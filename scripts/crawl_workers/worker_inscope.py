"""In-scope 보강 워커: 채점 5카테고리 중 공지/학사일정/졸업요건만 더 모은다.

기존 worker_service2.py / crawlers.notices / crawlers.academic 와 동일 패턴:
  - requests.Session + 재시도(서버 일시적 TLS/연결리셋 흡수)
  - 본문 추출은 crawler_pipeline.body_extractor (fetch_html/extract_main_text/fetch_post)
  - 모지바케는 repair_encoding 으로 per-doc 복구 (한글 늘 때만 교체)
  - time.sleep(0.15) 서버 부담 방지, 도메인당 MAX_* 상한

대상 (off-scope 학과소개/교수진/연구실은 크롤 안 함):
  - 공지(K_notices)   : 학과 공지/공고 게시판 상세글 (장학/취업/행사 공고 포함)
  - 졸업요건(F_department): 학과 교육과정/졸업요건/이수체계 페이지 (학과별)
  - 학사일정(B_academic) : 학과 학사일정/학사력 성격 페이지

학과 게시판/교과과정 경로는 학과마다 달라(community/notice, news/notice01,
square/notice01, curriculum/system, edu/requirements ...) 하드코딩 대신
학과 홈에서 키워드로 자동 탐색한다.

사용:  python worker_inscope.py            (전체 DEPTS)
       python worker_inscope.py computer   (특정 학과 slug만)
출력:  data/crawled_staging/inscope_{slug}.json + .done
"""
import sys, json, time, re
from pathlib import Path
from urllib.parse import urljoin, urlparse
from datetime import datetime, timedelta

ROOT = Path('C:/Users/dmsak/cnu-llm-bot')
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

import requests
from bs4 import BeautifulSoup
from crawler_pipeline.body_extractor import fetch_html, extract_main_text, fetch_post
from crawler_pipeline.text_repair import repair_encoding

NOW = datetime.utcnow().isoformat()
TODAY = NOW[:10]
# 공지는 시의성, 졸업요건/일정은 semi-static
VALID_NOTICE = (datetime.utcnow() + timedelta(days=7)).isoformat()
VALID_STATIC = (datetime.utcnow() + timedelta(days=30)).isoformat()

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/120.0 Safari/537.36',
    'Accept-Language': 'ko-KR,ko;q=0.9',
}
SESS = requests.Session()
SESS.headers.update(HEADERS)

SKIP_TITLES = {'다음글', '이전글', '목록', '처음', '이전', '다음', '마지막',
               '검색', '더보기', '글쓰기', '답변', '수정', '삭제', '인쇄'}
SKIP_KW = ['바로가기', '주메뉴', '서브메뉴', '본문 바로가기', '사이트맵', '로그인',
           '통합검색', '발전기금', '번역이 완료']

# 게시판 목록행에서 상세글 링크 패턴
DETAIL_RE = re.compile(r"(articleNo=|mode=view|[?&]no=\d)")
# 졸업요건/교육과정/이수체계 페이지로 인정할 경로/텍스트 키워드
CURRICULUM_KW = ['curriculum', 'requirement', 'completion', 'system20',
                 'graduat', 'curri', 'course', '교육과정', '졸업', '이수',
                 '교과', '학점', '교과목']
# 학사일정 성격
CALENDAR_KW = ['calendar', 'schedule', '학사일정', '학사력', '학기일정', '일정']
# off-scope (절대 크롤 안 함): 학과소개/교수진/연구실/연혁/위치/인사말 등
OFFSCOPE_KW = ['professor', 'faculty', 'people', 'lab', 'research', 'history',
               'greeting', 'intro', 'location', 'organization', 'member',
               'staff', 'emeritus', '교수', '연구실', '연혁', '인사말', '오시는',
               '조직도', '소개']
# 영문 페이지(/en/, /english/)는 한글비율 게이트에서 어차피 탈락 → 사전 컷
ENGLISH_PATH_RE = re.compile(r'/(en|english|eng)/')
# 과거 이수체계도(system20YY) 중 오래된 연도는 near-dup/구버전 → 최신만 유지
OLD_SYSTEM_RE = re.compile(r'system(\d{4})')
CURRENT_YEAR = datetime.utcnow().year

MAX_NOTICE_DETAILS = 40   # 학과당 공지 상세글 상한
MAX_LIST_PAGES = 2        # 게시판 목록 페이지 수


# (slug, host, [board_paths])  board_path 는 학과 홈에서 자동탐색 실패시의 폴백
DEPTS = [
    ('computer', 'computer.cnu.ac.kr', ['/computer/notice/notice.do',
                                        '/computer/notice/bachelor.do',
                                        '/computer/notice/job.do']),
    ('ee',       'ee.cnu.ac.kr',       ['/ee/community/notice.do']),
    ('me',       'me.cnu.ac.kr',       ['/me/news/notice01.do']),
    ('biz',      'biz.cnu.ac.kr',      ['/biz/community/notice-02.do']),
    ('math',     'math.cnu.ac.kr',     ['/math/community/notice.do']),
    ('mse',      'mse.cnu.ac.kr',      ['/mse/square/notice01.do']),
    ('chem',     'chem.cnu.ac.kr',     []),
]


def get(url, tries=3, timeout=20):
    """일시적 TLS/연결리셋 흡수용 재시도 GET."""
    last = None
    for _ in range(tries):
        try:
            return SESS.get(url, timeout=timeout)
        except Exception as e:
            last = e
            time.sleep(0.8)
    raise last


def clean_text(text):
    """메뉴/네비 줄 제거 + 모지바케 복구."""
    text = repair_encoding(text or '')
    lines = [l for l in text.splitlines()
             if not any(kw in l for kw in SKIP_KW) and len(l.strip()) > 4]
    return '\n'.join(lines).strip()


def make_doc(url, category, title, text, notice=False):
    return {
        'source_url': url,
        'data_category': category,
        'last_crawled_at': NOW,
        'valid_until': VALID_NOTICE if notice else VALID_STATIC,
        'freshness_tier': 'time_sensitive' if notice else 'semi_static',
        'original_text': text,
        'title': title,
        'content': text,
        'date': TODAY,
    }


def discover_paths(slug, host, fallback_boards):
    """학과 홈에서 공지게시판/교육과정/학사일정 링크 자동탐색.

    반환: (notice_boards, curriculum_pages, calendar_pages) — 모두 절대 URL.
    off-scope(교수진/연구실 등)는 제외.
    """
    notices, curricula, calendars = set(), set(), set()
    for entry in (f'https://{host}/{slug}/index.do', f'https://{host}/'):
        try:
            r = get(entry)
            r.encoding = r.apparent_encoding or r.encoding
            soup = BeautifulSoup(r.text, 'html.parser')
        except Exception:
            continue
        for a in soup.find_all('a', href=True):
            href = a['href'].split('#')[0]
            if not href or href.startswith(('javascript', 'mailto')):
                continue
            full = urljoin(entry, href)
            if urlparse(full).netloc != host or '.do' not in full:
                continue
            low = (href + a.get_text(strip=True)).lower()
            base = full.split('?')[0]
            # off-scope / 영문 먼저 컷
            if any(k in base.lower() for k in OFFSCOPE_KW):
                continue
            if ENGLISH_PATH_RE.search(base.lower()):
                continue
            # 과거 이수체계도: 최근 2개년만 (구버전 near-dup 제거)
            ms = OLD_SYSTEM_RE.search(base.lower())
            if ms and int(ms.group(1)) < CURRENT_YEAR - 1:
                continue
            # notice 목록(.do) 만 (상세 articleNo/view 링크는 제외)
            if 'notice' in base.lower() and not DETAIL_RE.search(full):
                notices.add(base)
            if any(k in low for k in CALENDAR_KW):
                calendars.add(base)
            elif any(k in low for k in CURRICULUM_KW):
                curricula.add(base)
        if notices or curricula:
            break
    # 폴백 보드 합치기
    for b in fallback_boards:
        notices.add(f'https://{host}{b}')
    return sorted(notices), sorted(curricula), sorted(calendars)


def crawl_notice_board(board_url, host):
    """게시판 목록 → 상세글 링크 → fetch_post 로 본문. K_notices 문서 리스트."""
    docs, seen = [], set()
    for page in range(1, MAX_LIST_PAGES + 1):
        list_url = board_url + (f'?article.offset={(page-1)*10}&articleLimit=10'
                                if page > 1 else '')
        try:
            html = fetch_html(list_url, timeout=15)
            soup = BeautifulSoup(html, 'html.parser')
        except Exception:
            break
        rows = soup.select("td.subject a, .tit a, td a, .title a, a[href]")
        for a in rows:
            if len(docs) >= MAX_NOTICE_DETAILS:
                return docs
            title = a.get_text(strip=True)
            href = a.get('href', '')
            if not title or len(title) < 4 or title in SKIP_TITLES:
                continue
            if not DETAIL_RE.search(href):
                continue
            link = urljoin(board_url, href)
            if urlparse(link).netloc != host or link in seen:
                continue
            seen.add(link)
            post = fetch_post(link, timeout=15)
            if not post or not post['text'].strip():
                continue
            text = clean_text(post['text'])
            if len(text) < 120:
                continue
            docs.append(make_doc(link, 'K_notices', repair_encoding(post['title']),
                                 text, notice=True))
            time.sleep(0.15)
    return docs


def crawl_static(url, category):
    """교육과정/졸업요건/학사일정 단일 페이지 → 본문 추출."""
    try:
        html = fetch_html(url, timeout=15)
    except Exception:
        return None
    text = clean_text(extract_main_text(html, min_len=80) or '')
    if len(text) < 120:
        return None
    tm = re.search(r'<title[^>]*>([^<]+)</title>', html or '')
    title = repair_encoding(tm.group(1).strip()) if tm else url.rstrip('/').split('/')[-1]
    return make_doc(url, category,
                    title, text,
                    notice=False)


def sweep_dept(slug, host, fallback_boards):
    notices, curricula, calendars = discover_paths(slug, host, fallback_boards)
    print(f'  [{slug}] 탐색: 공지보드 {len(notices)} 교육과정 {len(curricula)} '
          f'학사일정 {len(calendars)}', flush=True)
    docs = []
    for b in notices:
        nd = crawl_notice_board(b, host)
        docs.extend(nd)
        print(f'    notice {b.replace("https://"+host,"")}: +{len(nd)}', flush=True)
        time.sleep(0.15)
    for u in curricula:
        d = crawl_static(u, 'F_department')
        if d:
            docs.append(d)
        time.sleep(0.15)
    for u in calendars:
        d = crawl_static(u, 'B_academic')
        if d:
            docs.append(d)
        time.sleep(0.15)
    return docs


def verify_docs(docs):
    """한글 코드포인트>0 && FFFD==0 무결성 검증."""
    han = sum(sum(1 for c in (d.get('content') or '') if '가' <= c <= '힣') for d in docs)
    fffd = sum((d.get('content') or '').count('�') for d in docs)
    return han, fffd


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    out_dir = ROOT / 'data/crawled_staging'
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for slug, host, boards in DEPTS:
        if only and only not in slug and only not in host:
            continue
        print(f'\n=== inscope {slug} ({host}) ===', flush=True)
        try:
            docs = sweep_dept(slug, host, boards)
        except Exception as e:
            print(f'  [{slug}] 실패: {type(e).__name__}: {e}', flush=True)
            docs = []
        tag = f'inscope_{slug}'
        with open(out_dir / f'{tag}.json', 'w', encoding='utf-8') as f:
            json.dump(docs, f, ensure_ascii=False, indent=2)
        (out_dir / f'{tag}.done').write_text(str(len(docs)), encoding='utf-8')
        han, fffd = verify_docs(docs)
        cats = {}
        for d in docs:
            cats[d['data_category']] = cats.get(d['data_category'], 0) + 1
        ok = 'OK' if (len(docs) == 0 or (han > 0 and fffd == 0)) else 'WARN'
        print(f'  완료: {len(docs)}건 {cats} → {tag}.json  [한글:{han} FFFD:{fffd} {ok}]',
              flush=True)
        results.append((tag, len(docs), cats, han, fffd, ok))

    print('\n=== 최종 결과 ===')
    total = 0
    for tag, cnt, cats, han, fffd, ok in results:
        total += cnt
        print(f'  {tag}.json docs={cnt} {cats} 한글={han} FFFD={fffd} [{ok}]')
    print(f'\n신규 총 문서 수: {total}')


if __name__ == '__main__':
    main()
