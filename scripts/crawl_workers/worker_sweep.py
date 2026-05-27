"""범용 sweep 워커: 도메인 한 개 받아서 .do/.html 페이지 BFS depth 2~3 크롤.

사용: python worker_sweep.py <도메인_호스트> <카테고리> [max_pages]
예: python worker_sweep.py cns.cnu.ac.kr F_department 200
출력: data/crawled_staging/sweep_{호스트}.json + .done
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
           '통합검색', 'CNU With U', '발전기금', '번역이 완료']
MAX_DEPTH = 3
DEFAULT_MAX_PAGES = 200


def crawl_page(url: str, category: str) -> dict | None:
    try:
        html = fetch_html(url, timeout=15)
    except Exception:
        return None, ''
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
        'source_url': url,
        'data_category': category,
        'last_crawled_at': NOW,
        'valid_until': VALID,
        'freshness_tier': 'semi_static',
        'original_text': text,
        'title': title,
        'content': text,
        'date': TODAY,
    }, html or ''


def discover_links(base: str, html: str) -> set[str]:
    found = set()
    for h in re.findall(r'href=[\"\']([^\"\'#?\s]+\.(?:do|html))[\"\']', html or ''):
        full = urljoin(base, h)
        if full.startswith(base):
            found.add(full)
    return found


def sweep(host: str, category: str, max_pages: int):
    base = f'https://{host}'
    docs = []
    seen = set()
    frontier = {base + '/', base}
    for depth in range(MAX_DEPTH):
        new_front = set()
        for url in list(frontier):
            if url in seen or len(seen) >= max_pages:
                continue
            seen.add(url)
            doc, html = crawl_page(url, category)
            if doc:
                docs.append(doc)
            for link in discover_links(base, html):
                if link not in seen:
                    new_front.add(link)
            time.sleep(0.15)
        print(f'  depth {depth+1}: visited={len(seen)} docs={len(docs)} next={len(new_front)}', flush=True)
        if not new_front or len(seen) >= max_pages:
            break
        frontier = new_front
    return docs


def main():
    if len(sys.argv) < 3:
        print('usage: worker_sweep.py <host> <category> [max_pages]')
        sys.exit(1)
    host = sys.argv[1]
    category = sys.argv[2]
    max_pages = int(sys.argv[3]) if len(sys.argv) >= 4 else DEFAULT_MAX_PAGES
    print(f'=== sweep {host} (cat={category}, max={max_pages}) ===', flush=True)
    docs = sweep(host, category, max_pages)
    out = ROOT / f'data/crawled_staging/sweep_{host.replace(".","_")}.json'
    done = ROOT / f'data/crawled_staging/sweep_{host.replace(".","_")}.done'
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(docs, f, ensure_ascii=False, indent=2)
    done.write_text(str(len(docs)), encoding='utf-8')
    print(f'\n완료: {len(docs)}건 → {out}', flush=True)


if __name__ == '__main__':
    main()
