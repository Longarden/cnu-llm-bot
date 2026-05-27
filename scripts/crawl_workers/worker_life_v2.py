"""생활 보강 워커: 기숙사/학생회/도서관/취업 깊이."""
import sys, json, time, re
from pathlib import Path
from urllib.parse import urljoin
from datetime import datetime, timedelta

ROOT = Path('C:/Users/dmsak/cnu-llm-bot')
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

from crawler_pipeline.body_extractor import fetch_html, extract_main_text
from crawler_pipeline.text_repair import repair_encoding

OUT = ROOT / 'data/crawled_staging/life_v2.json'
DONE = ROOT / 'data/crawled_staging/life_v2.done'

NOW = datetime.utcnow().isoformat()
VALID = (datetime.utcnow() + timedelta(days=30)).isoformat()
TODAY = NOW[:10]

# 영역별 seed URL + category. 도메인 내 .do/.html 페이지를 1depth BFS.
SOURCES = [
    ('https://dorm.cnu.ac.kr', 'G_dormitory', [
        '/dorm/intro/welcome.do', '/dorm/intro/history.do', '/dorm/intro/dorms.do',
        '/dorm/info/dorms.do', '/dorm/info/staff.do', '/dorm/info/rule.do',
        '/dorm/info/payment.do', '/dorm/recruit/calendar.do',
        '/dorm/community/notice.do', '/dorm/community/faq.do',
    ]),
    ('https://cnustudent.cnu.ac.kr', 'J_extracurricular', [
        '/cnustudent/intro/greetings.do', '/cnustudent/intro/duty.do',
        '/cnustudent/notice/notice.do', '/cnustudent/notice/event.do',
        '/cnustudent/student/info.do', '/cnustudent/club/list.do',
        '/cnustudent/club/notice.do', '/cnustudent/welfare/info.do',
    ]),
    ('https://library.cnu.ac.kr', 'A_library', [
        '/library/intro/intro.do', '/library/intro/history.do',
        '/library/usage/regulations.do', '/library/usage/hours.do',
        '/library/usage/loan.do', '/library/usage/facility.do',
        '/library/service/reservation.do', '/library/service/databases.do',
        '/library/notice/notice.do',
    ]),
    ('https://dream.cnu.ac.kr', 'E_career', [
        '/dream/intro/welcome.do', '/dream/intro/organization.do',
        '/dream/notice/notice.do', '/dream/notice/job.do',
        '/dream/program/list.do', '/dream/program/intern.do',
        '/dream/recruit/list.do', '/dream/data/info.do',
    ]),
    ('https://mobileadmin.cnu.ac.kr', 'H_facilities', [
        '/mobileadmin/intro/greetings.do',
        '/mobileadmin/intro/organ.do',
        '/mobileadmin/intro/location.do',
        '/mobileadmin/info/facility.do',
    ]),
]

SKIP_KW = ['바로가기', '주메뉴', '서브메뉴', '본문 바로가기', '사이트맵', '로그인',
           '통합검색', 'CNU With U', '발전기금']


def crawl_page(url: str, category: str) -> dict | None:
    try:
        html = fetch_html(url, timeout=15)
    except Exception:
        return None
    text = extract_main_text(html, min_len=80)
    if not text:
        return None
    text = repair_encoding(text)
    # SKIP_KW 라인 제거
    lines = [l for l in text.splitlines() if not any(kw in l for kw in SKIP_KW)]
    text = '\n'.join(l for l in lines if len(l.strip()) > 8)
    if len(text) < 120:
        return None
    # title from <title>
    tm = re.search(r'<title[^>]*>([^<]+)</title>', html or '')
    title = repair_encoding(tm.group(1).strip()) if tm else url.split('/')[-1].replace('.do', '')
    return {
        'source_url': url,
        'data_category': category,
        'last_crawled_at': NOW,
        'valid_until': VALID,
        'freshness_tier': 'semi_static',
        'original_text': text,
        'title': title,
        'content': text,
        'date': TODAY,
    }


def discover_links(base: str, html: str) -> set[str]:
    """domain 내부의 .do 또는 .html 링크 BFS용 수집."""
    found = set()
    if not html:
        return found
    for h in re.findall(r'href=[\"\']([^\"\'#?\s]+\.(?:do|html))[\"\']', html):
        full = urljoin(base, h)
        if full.startswith(base):
            found.add(full)
    return found


def main():
    all_docs = []
    for base, cat, paths in SOURCES:
        print(f'\n=== {base} ({cat}) ===', flush=True)
        # seed 페이지 크롤
        cnt = 0
        seen = set()
        for p in paths:
            url = base + p
            seen.add(url)
            d = crawl_page(url, cat)
            if d:
                all_docs.append(d)
                cnt += 1
                print(f'  OK {p}', flush=True)
            else:
                print(f'  skip {p}', flush=True)
            time.sleep(0.2)
        # seed 페이지에서 BFS 1depth (목록 페이지의 상세 링크)
        frontier_urls = []
        for p in paths:
            url = base + p
            try:
                html = fetch_html(url, timeout=10)
            except Exception:
                continue
            for link in discover_links(base, html or ''):
                if link not in seen:
                    seen.add(link)
                    frontier_urls.append(link)
            if len(frontier_urls) >= 30:
                break
        print(f'  BFS depth1: {len(frontier_urls[:30])}개 추가 탐색', flush=True)
        for url in frontier_urls[:30]:
            d = crawl_page(url, cat)
            if d:
                all_docs.append(d)
                cnt += 1
            time.sleep(0.15)
        print(f'  소계 {cnt}건', flush=True)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(all_docs, f, ensure_ascii=False, indent=2)
    DONE.write_text(str(len(all_docs)), encoding='utf-8')
    print(f'\n완료: {len(all_docs)}건 → {OUT}', flush=True)


if __name__ == '__main__':
    main()
