"""입학처 깊이 워커: BFS depth 3."""
import sys, json, re
from pathlib import Path
from urllib.parse import urljoin

ROOT = Path('C:/Users/dmsak/cnu-llm-bot')
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

from scripts.collect_regulations_admission import collect_ipsi, fetch_utf8

OUT = ROOT / 'data/crawled_staging/admission_v2.json'
DONE = ROOT / 'data/crawled_staging/admission_v2.done'

IPSI_PREFIX = 'https://ipsi.cnu.ac.kr/html/'
SEEDS = [
    'https://ipsi.cnu.ac.kr/html/uadm/',
    'https://ipsi.cnu.ac.kr/html/gadm/',
    'https://ipsi.cnu.ac.kr/html/info/',
    'https://ipsi.cnu.ac.kr/html/comm/',
    'https://ipsi.cnu.ac.kr/html/intro/',
    'https://ipsi.cnu.ac.kr/html/foreign/',
]
MAX_DEPTH = 3
MAX_PAGES = 500


def deep_discover():
    discovered = set()
    frontier = set(SEEDS)
    for depth in range(MAX_DEPTH):
        new_frontier = set()
        for u in list(frontier):
            if u in discovered or len(discovered) >= MAX_PAGES:
                continue
            discovered.add(u)
            html = fetch_utf8(u)
            if not html:
                continue
            for h in re.findall(r'href=[\"\']([^\"\'#?]+\.html)[\"\']', html):
                full = urljoin(u, h)
                if full.startswith(IPSI_PREFIX) and full not in discovered:
                    new_frontier.add(full)
        print(f'  depth {depth+1}: discovered={len(discovered)} new={len(new_frontier)}', flush=True)
        if not new_frontier:
            break
        frontier = new_frontier
    return sorted(discovered)


def main():
    urls = deep_discover()
    print(f'\n입학처 후보 URL: {len(urls)}건', flush=True)
    docs, _ = collect_ipsi(urls)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(docs, f, ensure_ascii=False, indent=2)
    DONE.write_text(str(len(docs)), encoding='utf-8')
    print(f'\n완료: {len(docs)}건 → {OUT}', flush=True)


if __name__ == '__main__':
    main()
