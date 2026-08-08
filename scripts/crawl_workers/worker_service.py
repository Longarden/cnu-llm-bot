"""서비스 도메인 전용 워커: JS 리다이렉트 추적 + 범용 본문 추출.

학과 도메인과 달리 counselling/gymn/job/dorm/library 등은
- 루트가 location.href JS 리다이렉트 셸이거나
- trafilatura/board_view 셀렉터에 안 걸리는 구조라
일반 sweep이 0건이었음. 이 워커는 리다이렉트를 따라가고,
개선된 extract_main_text(3차 범용 폴백 포함)로 본문을 뽑는다.

사용: python worker_service.py            (전체 SOURCES)
      python worker_service.py counselling (특정 호스트만)
출력: data/crawled_staging/service_{host}.json + .done
"""
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

NOW = datetime.utcnow().isoformat()
VALID = (datetime.utcnow() + timedelta(days=30)).isoformat()
TODAY = NOW[:10]

SKIP_KW = ['바로가기', '주메뉴', '서브메뉴', '본문 바로가기', '사이트맵', '로그인',
           '통합검색', 'CNU With U', '발전기금', '번역이 완료', '바로가기 >']
MAX_DEPTH = 3
MAX_PAGES = 220

# host, category, [entry paths]  — 리다이렉트 후 실제 진입점
SOURCES = [
    ('counselling.cnu.ac.kr', 'G_student_life', ['/index.do']),
    ('gymn.cnu.ac.kr',        'H_facilities',   ['/index.do', '/']),
    ('job.cnu.ac.kr',         'E_career',       ['/job/index.do']),
    ('dorm.cnu.ac.kr',        'G_dormitory',    ['/html/kr/', '/html/kr/dorm/dorm_0101.html']),
    ('library.cnu.ac.kr',     'A_library',      ['/', '/content/menu.do']),
    ('dream.cnu.ac.kr',       'E_career',       ['/dream/index.do', '/']),
    ('stuserv.cnu.ac.kr',     'G_student_life', ['/index.do', '/']),
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


def discover_links(base, html):
    found = set()
    for h in re.findall(r'href=["\']([^"\'#?\s]+\.(?:do|html))["\']', html or ''):
        full = urljoin(base, h)
        if full.startswith(base):
            found.add(full)
    return found


def sweep_host(host, category, entries):
    base = f'https://{host}'
    docs, seen = [], set()
    # 진입점에서 리다이렉트 추적 후 1차 링크 수집
    frontier = set()
    for e in entries:
        u = base + e
        seen.add(u)
        doc, html = crawl_page(u, category)
        if doc:
            docs.append(doc)
        frontier |= discover_links(base, html)
    frontier -= seen
    for depth in range(MAX_DEPTH):
        new_front = set()
        for url in list(frontier):
            if url in seen or len(seen) >= MAX_PAGES:
                continue
            seen.add(url)
            doc, html = crawl_page(url, category)
            if doc:
                docs.append(doc)
            new_front |= discover_links(base, html)
            time.sleep(0.12)
        new_front -= seen
        print(f'  {host} depth{depth+1}: visited={len(seen)} docs={len(docs)} next={len(new_front)}', flush=True)
        if not new_front or len(seen) >= MAX_PAGES:
            break
        frontier = new_front
    return docs


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    out_dir = ROOT / 'data/crawled_staging'
    out_dir.mkdir(parents=True, exist_ok=True)
    for host, cat, entries in SOURCES:
        if only and only not in host:
            continue
        print(f'=== service {host} ({cat}) ===', flush=True)
        docs = sweep_host(host, cat, entries)
        tag = host.replace('.', '_')
        with open(out_dir / f'service_{tag}.json', 'w', encoding='utf-8') as f:
            json.dump(docs, f, ensure_ascii=False, indent=2)
        (out_dir / f'service_{tag}.done').write_text(str(len(docs)), encoding='utf-8')
        print(f'  완료: {len(docs)}건 → service_{tag}.json\n', flush=True)


if __name__ == '__main__':
    main()
