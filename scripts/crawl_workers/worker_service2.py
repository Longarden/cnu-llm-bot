"""서비스 도메인 확장 워커 2: 빈약 카테고리 보강.

대상:
  - library.cnu.ac.kr  → A_library   (webcontent/info, bbs/content 경로 지원)
  - plus.cnu.ac.kr     → A_shuttle / D_scholarship / H_facilities / G_student_life
  - mobileadmin.cnu.ac.kr → A_dining
  - cnustudent.cnu.ac.kr  → G_student_life / J_extracurricular

기존 worker_service.py 와 동일 패턴:
  - JS 리다이렉트 추적
  - extract_main_text (3차 범용 폴백)
  - time.sleep(0.15) 서버 부담 방지
  - MAX_PAGES 200 내외

출력: data/crawled_staging/service2_{tag}.json + .done
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

from crawler_pipeline.body_extractor import fetch_html, extract_main_text
from crawler_pipeline.text_repair import repair_encoding

NOW = datetime.utcnow().isoformat()
VALID = (datetime.utcnow() + timedelta(days=30)).isoformat()
TODAY = NOW[:10]

SKIP_KW = ['바로가기', '주메뉴', '서브메뉴', '본문 바로가기', '사이트맵', '로그인',
           '통합검색', 'CNU With U', '발전기금', '번역이 완료', '바로가기 >',
           '삭제 후 코딩 해주세요']
MAX_DEPTH = 3
MAX_PAGES = 200

# (label, host, category, [entry_paths], extra_seeds)
# extra_seeds: 진입점 BFS 외에 직접 시드로 추가할 절대 URL 목록
SOURCES = [
    # 1. library: webcontent/info + bbs/content + bbs/list 경로
    (
        'library2',
        'library.cnu.ac.kr',
        'A_library',
        [
            '/webcontent/info/2',   # 이용안내
            '/webcontent/info/3',   # 대출/반납
            '/webcontent/info/4',
            '/webcontent/info/5',
            '/webcontent/info/6',
            '/webcontent/info/7',
            '/webcontent/info/8',
            '/webcontent/info/9',
            '/webcontent/info/11',
            '/webcontent/info/12',
            '/webcontent/info/13',
            '/webcontent/info/14',
            '/webcontent/info/15',
            '/webcontent/info/16',
            '/webcontent/info/18',
            '/webcontent/info/19',
            '/webcontent/info/20',
            '/webcontent/info/21',
            '/webcontent/info/23',
            '/webcontent/info/24',
            '/webcontent/info/27',
            '/webcontent/info/28',
            '/webcontent/info/29',
            '/webcontent/info/33',
            '/webcontent/info/34',
            '/webcontent/info/35',
            '/webcontent/info/36',
            '/webcontent/info/37',
            '/webcontent/info/38',
            '/webcontent/info/39',
            '/webcontent/info/41',
            '/webcontent/info/42',
            '/webcontent/info/43',
            '/webcontent/info/44',
            '/webcontent/info/60',
            '/webcontent/info/61',
            '/webcontent/info/62',
            '/webcontent/info/64',
            '/webcontent/info/66',
            '/webcontent/info/67',
            '/webcontent/info/68',
            '/webcontent/info/70',
            '/webcontent/info/71',
            '/webcontent/info/72',
            '/webcontent/info/73',
            '/webcontent/info/74',
            '/webcontent/info/75',
            '/webcontent/info/76',
            '/webcontent/info/77',
            '/webcontent/info/78',
            '/webcontent/info/130',
            '/webcontent/info/210',
            '/webcontent/info/230',
            '/webcontent/info/250',
            '/webcontent/info/251',
            '/webcontent/info/290',
            '/webcontent/info/310',
            '/webcontent/info/312',
            '/webcontent/info/313',
            '/webcontent/info/314',
            '/webcontent/info/315',
            '/webcontent/info/317',
            '/webcontent/info/318',
            '/webcontent/info/320',
            '/webcontent/info/321',
            '/webcontent/info/322',
            '/webcontent/info/324',
            '/webcontent/info/325',
            '/webcontent/info/326',
            '/webcontent/info/327',
            '/webcontent/info/328',
            '/webcontent/info/329',
            '/webcontent/info/330',
            '/webcontent/info/331',
            '/webcontent/info/332',
            '/webcontent/info/333',
            '/webcontent/info/334',
            '/webcontent/info/335',
            '/webcontent/info/336',
            '/webcontent/info/337',
            '/webcontent/info/338',
            '/webcontent/info/339',
            '/webcontent/info/340',
            '/webcontent/info/341',
            '/webcontent/info/343',
            '/webcontent/info/344',
            '/webcontent/info/345',
            '/webcontent/info/346',
            '/webcontent/info/348',
            '/webcontent/info/350',
            '/webcontent/info/351',
            '/webcontent/info/353',
            '/bbs/list/1',
            '/bbs/list/2',
            '/bbs/list/5',
            '/bbs/list/7',
            '/bbs/list/9',
            '/bbs/list/11',
            '/bbs/list/25',
            '/bbs/list/26',
            '/bbs/list/27',
            '/bbs/list/28',
            '/bbs/list/32',
            '/bbs/list/34',
            '/bbs/list/35',
            '/bbs/list/36',
            '/bbs/list/42',
            '/bbs/list/43',
            '/bbs/list/44',
            '/bbs/list/45',
            '/education/list',
            '/faqlib/faq',
        ],
        [],
    ),
    # 2. plus.cnu.ac.kr - shuttle (A_shuttle)
    (
        'plus_shuttle',
        'plus.cnu.ac.kr',
        'A_shuttle',
        [
            '/html/kr/sub05/sub05_050403.html',  # 학교셔틀버스
            '/html/kr/sub05/sub05_050410.html',  # 통학버스 관련 추가 페이지
            '/html/kr/sub05/sub05_050401.html',  # 학생증
        ],
        [],
    ),
    # 3. plus.cnu.ac.kr - scholarship (D_scholarship)
    # 장학게시판은 동적 board(menu_dvs_cd=0713)이므로 sub01 장학 관련 정적 페이지 수집
    (
        'plus_scholarship',
        'plus.cnu.ac.kr',
        'D_scholarship',
        [
            '/html/kr/sub01/sub01_010701.html',  # 장학/등록금 관련
            '/html/kr/sub01/sub01_010702.html',
            '/html/kr/sub01/sub01_01070401.html',
            '/html/kr/sub01/sub01_01071204.html',
            '/html/kr/sub01/sub01_01071301.html',
            '/html/kr/sub01/sub01_01071501.html',
        ],
        [],
    ),
    # 4. plus.cnu.ac.kr - student life / facilities
    (
        'plus_student',
        'plus.cnu.ac.kr',
        'G_student_life',
        [
            '/html/kr/sub05/sub05_050101.html',  # 교학처
            '/html/kr/sub05/sub05_050102.html',
            '/html/kr/sub05/sub05_050104.html',
            '/html/kr/sub05/sub05_05020101.html',
            '/html/kr/sub05/sub05_05020103.html',
            '/html/kr/sub05/sub05_050202.html',
            '/html/kr/sub05/sub05_050404.html',  # 국제교류
            '/html/kr/sub05/sub05_05040201.html',
            '/html/kr/sub05/sub05_05050101.html',
            '/html/kr/sub05/sub05_050504.html',
            '/html/kr/sub05/sub05_050505.html',
            '/html/kr/sub05/sub05_050508.html',
            '/html/kr/sub05/sub05_050701.html',
            '/html/kr/sub05/sub05_050702.html',
            '/html/kr/sub05/sub05_050703.html',
            '/html/kr/sub05/sub05_050704.html',
            '/html/kr/sub05/sub05_050710.html',
            '/html/kr/sub01/sub01_010101.html',
            '/html/kr/sub01/sub01_010104.html',
            '/html/kr/sub01/sub01_0102.html',
            '/html/kr/sub01/sub01_010301.html',
            '/html/kr/sub01/sub01_010401.html',
            '/html/kr/sub01/sub01_010501.html',
            '/html/kr/sub01/sub01_010502.html',
            '/html/kr/sub01/sub01_010503.html',
            '/html/kr/sub01/sub01_01050509_01.html',
            '/html/kr/sub01/sub01_010601.html',
            '/html/kr/sub01/sub01_010602.html',
            '/html/kr/sub01/sub01_010605.html',
            '/html/kr/sub01/sub01_010801.html',
            '/html/kr/sub01/sub01_01080301.html',
            '/html/kr/sub01/sub01_010804.html',
            '/html/kr/sub02/sub02_020118.html',
            '/html/kr/sub02/sub02_020201.html',
            '/html/kr/sub02/sub02_020308.html',
            '/html/kr/sub02/sub02_020406.html',
        ],
        [],
    ),
    # 5. mobileadmin.cnu.ac.kr - dining
    (
        'mobileadmin_dining',
        'mobileadmin.cnu.ac.kr',
        'A_dining',
        ['/food/index.jsp'],
        [],
    ),
    # 6. cnustudent.cnu.ac.kr - student life / extracurricular
    (
        'cnustudent2',
        'cnustudent.cnu.ac.kr',
        'G_student_life',
        [
            '/cnustudent/notice/notice.do',
            '/cnustudent/notice/calendar.do',
            '/cnustudent/notice/cooperation.do',
            '/cnustudent/notice/cooper_appear.do',
            '/cnustudent/notice/cooper_edu.do',
            '/cnustudent/notice/cooper_food.do',
            '/cnustudent/notice/cooper_sports.do',
            '/cnustudent/notice/facilities.do',
            '/cnustudent/notice/bus_route.do',
            '/cnustudent/community/integ_notice.do',
            '/cnustudent/community/integ_board.do',
            '/cnustudent/community/integ_main.do',
            '/cnustudent/minutes/meeting-log01.do',
            '/cnustudent/intro/location.do',
            '/cnustudent/accessio.do',
        ],
        [],
    ),
]


def follow_redirect(url, html):
    """location.href JS 리다이렉트 셸이면 목적지로 한 번 더 이동."""
    if html and len(html) < 1200 and 'location.href' in html:
        m = re.search(r'location\.href\s*=\s*["\']([^"\']+)', html)
        if m:
            tgt = urljoin(url, m.group(1))
            try:
                return tgt, fetch_html(tgt, timeout=15)
            except Exception:
                pass
    return url, html


def crawl_page(url, category):
    try:
        html = fetch_html(url, timeout=15)
    except Exception:
        return None, ''
    url, html = follow_redirect(url, html)
    text = extract_main_text(html, min_len=80)
    if not text:
        return None, html or ''
    text = repair_encoding(text)
    lines = [l for l in text.splitlines() if not any(kw in l for kw in SKIP_KW)]
    text = '\n'.join(l for l in lines if len(l.strip()) > 8)
    if len(text) < 120:
        return None, html or ''
    tm = re.search(r'<title[^>]*>([^<]+)</title>', html or '')
    title = repair_encoding(tm.group(1).strip()) if tm else url.rstrip('/').split('/')[-1]
    return {
        'source_url': url, 'data_category': category,
        'last_crawled_at': NOW, 'valid_until': VALID,
        'freshness_tier': 'semi_static', 'original_text': text,
        'title': title, 'content': text, 'date': TODAY,
    }, html or ''


def discover_links(base_url, html, host):
    """href에서 같은 호스트 내 링크 수집.
    .do / .html / .jsp / extensionless path (/webcontent/info/N, /bbs/content/N 등) 모두 허용.
    """
    found = set()
    parsed_base = urlparse(base_url)
    base_scheme_host = f"{parsed_base.scheme}://{parsed_base.netloc}"

    for href in re.findall(r'href=["\']([^"\'#\s]+)["\']', html or ''):
        href = href.split('?')[0].split('#')[0]
        if not href:
            continue
        # 절대 URL
        if href.startswith('http'):
            parsed = urlparse(href)
            if parsed.netloc == host:
                found.add(href.split('?')[0].split('#')[0])
            continue
        # 상대 경로
        if href.startswith('/'):
            full = base_scheme_host + href
            found.add(full)
        elif href.startswith('./') or not href.startswith('//'):
            full = urljoin(base_url, href)
            if urlparse(full).netloc == host:
                found.add(full)
    return found


def is_content_url(url):
    """BFS 대상으로 포함할 URL 판별 - 명백한 비콘텐츠(이미지/css/js/외부링크) 제외."""
    path = urlparse(url).path.lower()
    skip_exts = ('.css', '.js', '.jpg', '.jpeg', '.png', '.gif', '.svg',
                 '.ico', '.pdf', '.zip', '.hwp', '.xlsx', '.docx', '.pptx')
    if any(path.endswith(e) for e in skip_exts):
        return False
    skip_paths = ('/login', '/logout', '/mylib', '/myloan', '/mypage',
                  '/myreserve', '/mypreserve', '/mylist', '/mynotice',
                  '/myprofile', '/myreview', '/mytag', '/myrecom',
                  '/sdi/', '/outlink', '/image/', '/style/', '/script/',
                  '/searchWeb', '/eds/', '/donors', '/statistics',
                  '/purchaserequest', '/otherlib', '/dds/', '/ill/',
                  '/loanreq', '/search/detail', '/search/tot',
                  '/search/arz', '/search/caz', '/search/ebz',
                  '/newarrival', '/newbook', '/digicol')
    if any(p in urlparse(url).path for p in skip_paths):
        return False
    return True


def sweep_host(label, host, category, entry_paths, extra_seeds):
    base = f'https://{host}'
    docs, seen = [], set()
    frontier = set()

    # 진입점 직접 크롤 + 링크 수집
    for e in entry_paths:
        u = base + e
        if u in seen:
            continue
        seen.add(u)
        doc, html = crawl_page(u, category)
        if doc:
            docs.append(doc)
        lnks = discover_links(u, html, host)
        frontier |= {l for l in lnks if is_content_url(l)}
        time.sleep(0.15)

    # extra seeds
    for u in extra_seeds:
        if u not in seen:
            seen.add(u)
            doc, html = crawl_page(u, category)
            if doc:
                docs.append(doc)
            lnks = discover_links(u, html, host)
            frontier |= {l for l in lnks if is_content_url(l)}
            time.sleep(0.15)

    frontier -= seen

    # BFS
    for depth in range(MAX_DEPTH):
        new_front = set()
        for url in list(frontier):
            if url in seen or len(seen) >= MAX_PAGES:
                continue
            seen.add(url)
            doc, html = crawl_page(url, category)
            if doc:
                docs.append(doc)
            lnks = discover_links(url, html, host)
            new_front |= {l for l in lnks if is_content_url(l)}
            time.sleep(0.15)
        new_front -= seen
        print(f'  [{label}] depth{depth+1}: visited={len(seen)} docs={len(docs)} next={len(new_front)}',
              flush=True)
        if not new_front or len(seen) >= MAX_PAGES:
            break
        frontier = new_front

    return docs


def verify_docs(docs):
    """한글 코드포인트 수 > 0 && FFFD(치환문자) == 0 검증."""
    hangul_total = sum(
        sum(1 for c in (d.get('content') or '') if '가' <= c <= '힣')
        for d in docs
    )
    fffd_total = sum(
        (d.get('content') or '').count('�')
        for d in docs
    )
    return hangul_total, fffd_total


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    out_dir = ROOT / 'data/crawled_staging'
    out_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for label, host, cat, entries, seeds in SOURCES:
        if only and only not in label and only not in host:
            continue
        print(f'\n=== service2 {label} ({host}, {cat}) ===', flush=True)
        docs = sweep_host(label, host, cat, entries, seeds)
        tag = f'service2_{label}'
        out_path = out_dir / f'{tag}.json'
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(docs, f, ensure_ascii=False, indent=2)
        (out_dir / f'{tag}.done').write_text(str(len(docs)), encoding='utf-8')
        hangul, fffd = verify_docs(docs)
        ok = 'OK' if (len(docs) == 0 or (hangul > 0 and fffd == 0)) else 'WARN'
        print(f'  완료: {len(docs)}건 → {tag}.json  [한글:{hangul} FFFD:{fffd} {ok}]',
              flush=True)
        results.append((tag, len(docs), hangul, fffd, ok))

    print('\n=== 최종 결과 ===')
    total = 0
    for tag, cnt, h, f, ok in results:
        total += cnt
        print(f'  {tag}.json  docs={cnt}  한글={h}  FFFD={f}  [{ok}]')
    print(f'\n신규 총 문서 수: {total}')


if __name__ == '__main__':
    main()
