"""static2 정적 보강 워커: 약한 채점 카테고리(학사일정/셔틀/식단)의 '정적' 콘텐츠만 수집.

공지(K_notices)는 충분하니 제외. 아래 3개의 '정적' 안내 페이지에 집중한다:
  - B_academic(학사일정/학사력/수강·시험·방학 일정, 교육과정·졸업요건 해설)
  - A_shuttle (통학/셔틀 시간표·노선·정류장, 주차안내)
  - A_dining  (구내식당 원산지/운영안내, 생활관 식당 서비스 — 일일 메뉴 자체는 동적이라 제외)

설계: BFS 대신 '큐레이트 URL' 방식. probe_static2*.py 로 미리 발굴한 plus.cnu.ac.kr
sub05 정적 메뉴 + 학사일정 academic_calendar + mobileadmin food + dorm 식당 서비스만 친다.
혼합 포털 BFS 가 seed 카테고리를 모든 링크에 도장찍어 오분류 ~50% 나던 문제를 회피.

본문 추출은 crawler_pipeline.body_extractor(fetch_html/extract_main_text, JS리다이렉트+범용폴백),
모지바케는 per-doc repair_encoding 으로 복구(한글 늘 때만). time.sleep(0.15) 서버 부담 방지.

off-scope(학과소개/교수/연구실/연혁/인사말 등)는 URL 큐레이션 단계에서 이미 배제됨.

사용:  python worker_static2.py            (전체)
       python worker_static2.py academic  (B_academic 만)
       python worker_static2.py shuttle   (A_shuttle 만)
       python worker_static2.py dining    (A_dining 만)
출력:  data/crawled_staging/static2_academic.json / static2_shuttle.json / static2_dining.json (+ .done)
"""
import sys, json, time, re, html as _html
from pathlib import Path
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
TODAY = NOW[:10]
# 학사일정/셔틀/식단 정적 안내는 학기 단위로 갱신 → 90일 유효(static)
VALID = (datetime.utcnow() + timedelta(days=90)).isoformat()

SKIP_KW = ['바로가기', '주메뉴', '서브메뉴', '본문 바로가기', '사이트맵', '로그인',
           '통합검색', 'CNU With U', '발전기금', '번역이 완료', '바로가기 >',
           'TAB MENU', 'TAB', '이전글', '다음글', '목록', 'print', '인쇄',
           'QUICK', '퀵메뉴', 'FAMILY SITE', '패밀리사이트', 'top', 'TOP']
MIN_LEN = 120

PLUS = 'https://plus.cnu.ac.kr/html/kr/sub05'

# (category, key, url, title_hint)  — probe 로 본문 확인된 정적 페이지만.
TARGETS = {
    'academic': [
        ('B_academic', 'cal',
         'https://plus.cnu.ac.kr/_prog/academic_calendar/?site_dvs_cd=kr&menu_dvs_cd=05020101',
         '충남대 학사일정(학사력)'),
        ('B_academic', 'guide', f'{PLUS}/sub05_05020101.html', '충남대 학사안내'),
        ('B_academic', 'biz',   f'{PLUS}/sub05_050202.html',   '충남대 학사업무안내'),
        ('B_academic', 'grad',  f'{PLUS}/sub05_051202.html',   '충남대 졸업이수학점'),
        ('B_academic', 'curri', f'{PLUS}/sub05_051201.html',   '충남대 교육과정 해설'),
        ('B_academic', 'major', f'{PLUS}/sub05_051204.html',   '충남대 전공과정'),
        ('B_academic', 'conv',  f'{PLUS}/sub05_051205.html',   '충남대 융복합창의전공'),
        ('B_academic', 'dbl',   f'{PLUS}/sub05_051206.html',   '충남대 복수전공'),
        ('B_academic', 'minor', f'{PLUS}/sub05_051207.html',   '충남대 부전공'),
        ('B_academic', 'teach', f'{PLUS}/sub05_051208.html',   '충남대 교직과정'),
        ('B_academic', 'lifelong', f'{PLUS}/sub05_051209.html', '충남대 평생교육사 과정'),
        ('B_academic', 'gradsch', f'{PLUS}/sub05_05020103.html', '충남대 전문·특수대학원 학사일정'),
    ],
    'shuttle': [
        ('A_shuttle', 'bus',  f'{PLUS}/sub05_050403.html',   '충남대 학교셔틀버스(통학/순환버스) 시간표·노선'),
        ('A_shuttle', 'park', f'{PLUS}/sub05_05040201.html', '충남대 교내 주차안내'),
    ],
    'dining': [
        ('A_dining', 'food', 'https://mobileadmin.cnu.ac.kr/food/index.jsp',
         '충남대 구내식당 원산지·운영안내'),
        ('A_dining', 'dorm', 'https://dorm.cnu.ac.kr/html/kr/sub04/sub04_040301.html',
         '충남대 학생생활관 식당 서비스 안내'),
    ],
}

# 식당 일일메뉴(동적)는 제외하고 '정적 정보성' 구간만 남기는 키워드.
# 원산지/운영안내/이용시간/위치 등 학기 고정 정보만 통과.
DINING_STATIC_KW = ['원산지', '운영', '이용', '시간', '위치', '안내', '식당', '건강',
                    '정성', '위생', '친절', '학생회관', '생활관', '메뉴판', '가격']


def clean_text(text):
    """메뉴/네비/탭 줄 제거 + per-doc 모지바케 복구."""
    text = repair_encoding(text or '')
    lines = []
    for l in text.splitlines():
        s = l.strip()
        if not s or len(s) <= 2:
            continue
        if any(kw in s for kw in SKIP_KW) and len(s) < 30:
            continue
        # 메뉴 경로 표시줄(A > B > C) 컷
        if s.count('>') >= 2 and len(s) < 40:
            continue
        lines.append(s)
    return '\n'.join(lines).strip()


def fetch_title(html, fallback):
    tm = re.search(r'<title[^>]*>([^<]+)</title>', html or '')
    if tm:
        # HTML 엔티티 디코드(&gt; → >) 후 브레드크럼 앞부분만.
        t = repair_encoding(_html.unescape(tm.group(1)).strip())
        t = re.split(r'\s*>\s*', t)[0].strip()
        if t and t != '충남대학교' and len(t) >= 2:
            return f'충남대 {t}' if not t.startswith('충남대') else t
    return fallback


# 추출 실패 셸 페이지(JS 렌더): 본문이 공통 헤더 보일러플레이트로만 채워진 경우.
_SHELL_BOILER = 'THE STRONG CNU'


def is_shell_page(text):
    """본문이 'THE STRONG CNU' 헤더 보일러플레이트로 과반이면 셸 페이지."""
    if not text:
        return True
    n = text.count(_SHELL_BOILER)
    # 보일러플레이트가 3회 이상 반복되고 본문이 짧으면 실패 셸로 판단
    return n >= 3 and len(text) < 600


def make_doc(url, category, title, text):
    return {
        'source_url': url,
        'data_category': category,
        'last_crawled_at': NOW,
        'valid_until': VALID,
        'freshness_tier': 'static',
        'original_text': text,
        'title': title,
        'content': text,
        'date': TODAY,
    }


def crawl_calendar(url, title_hint):
    """학사일정 academic_calendar: 전체 + 월별 청크로 분할(검색 적중 ↑)."""
    try:
        html = fetch_html(url, timeout=20)
    except Exception:
        return []
    text = clean_text(extract_main_text(html, min_len=40) or '')
    if len(text) < MIN_LEN:
        return []
    docs = []
    # 전체 학사력 1건
    docs.append(make_doc(url, 'B_academic', f'{title_hint} 전체',
                         '충남대학교 학사일정(학사력)입니다.\n' + text))
    # 월별 청크: "NN월" 헤더로 분할
    parts = re.split(r'\n(?=\d{1,2}월\b)', text)
    for p in parts:
        p = p.strip()
        m = re.match(r'(\d{1,2})월', p)
        if not m or len(p) < MIN_LEN:
            continue
        mm = m.group(1)
        docs.append(make_doc(url, 'B_academic',
                             f'충남대 {mm}월 학사일정',
                             f'충남대학교 {mm}월 학사일정입니다.\n' + p))
    return docs


def crawl_static(url, category, title_hint, dining_filter=False):
    """단일 정적 페이지 → 본문 추출 → 정제 → doc 1건(또는 식단 필터 적용)."""
    try:
        html = fetch_html(url, timeout=20)
    except Exception:
        return []
    raw = extract_main_text(html, min_len=40)
    if not raw:
        return []
    text = clean_text(raw)
    if dining_filter:
        # 일일메뉴(동적) 라인 제거: 정적 정보 키워드 포함 줄 + 그 인접 맥락만 유지.
        # 보수적으로: 원산지/운영안내 블록만 남김(식재료 원산지 ~ 운영안내 끝).
        keep = [l for l in text.splitlines()
                if any(k in l for k in DINING_STATIC_KW) or len(l) > 25]
        # 일일 식단표 잔재(조식/중식/석식 + 짧은 음식명 나열) 컷
        keep = [l for l in keep if l.strip() not in ('조식', '중식', '석식', '운영안함')]
        text = '\n'.join(keep).strip()
    if len(text) < MIN_LEN or is_shell_page(text):
        return []
    # 식단 페이지 <title>('오늘의 식단','식당메뉴')은 동적 메뉴를 연상시켜 정적 문서엔 부적합
    # → 큐레이트한 정적 제목(title_hint) 강제. 그 외는 페이지 제목 우선.
    title = title_hint if dining_filter else fetch_title(html, title_hint)
    return [make_doc(url, category, title, text)]


def verify_docs(docs):
    """한글 코드포인트>0 && FFFD==0 무결성 검증."""
    han = sum(sum(1 for c in (d.get('content') or '') if '가' <= c <= '힣') for d in docs)
    fffd = sum((d.get('content') or '').count('�') for d in docs)
    return han, fffd


def run_group(group):
    docs = []
    for category, key, url, hint in TARGETS[group]:
        if key == 'cal':
            d = crawl_calendar(url, hint)
        else:
            d = crawl_static(url, category, hint, dining_filter=(group == 'dining'))
        docs.extend(d)
        print(f'  [{group}] {key:9s} +{len(d):2d}  {url}', flush=True)
        time.sleep(0.15)
    return docs


def main():
    only = sys.argv[1].lower() if len(sys.argv) > 1 else None
    out_dir = ROOT / 'data/crawled_staging'
    out_dir.mkdir(parents=True, exist_ok=True)
    groups = [only] if only in TARGETS else list(TARGETS.keys())

    results = []
    for group in groups:
        print(f'\n=== static2 {group} ===', flush=True)
        try:
            docs = run_group(group)
        except Exception as e:
            print(f'  [{group}] 실패: {type(e).__name__}: {e}', flush=True)
            docs = []
        tag = f'static2_{group}'
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
