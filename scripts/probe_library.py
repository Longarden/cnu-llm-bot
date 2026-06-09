"""library.cnu.ac.kr 링크 추출 - href 패턴 상세 파악."""
import sys, re
sys.path.insert(0, 'C:/Users/dmsak/cnu-llm-bot')
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

from crawler_pipeline.body_extractor import fetch_html, extract_main_text

html = fetch_html('https://library.cnu.ac.kr/', timeout=15)
print(f"html size: {len(html)}")

# Extract ALL hrefs
all_hrefs = re.findall(r'href=["\']([^"\']+)["\']', html)
print(f"Total hrefs: {len(all_hrefs)}")

# Show unique paths
paths = set()
for h in all_hrefs:
    if h.startswith('/') and not h.startswith('//'):
        paths.add(h.split('?')[0])
    elif 'library.cnu.ac.kr' in h:
        paths.add(h.split('?')[0])

print(f"\nUnique internal paths: {len(paths)}")
for p in sorted(paths):
    print(f"  {p}")

# Check sweep_library file for any found paths
import json
sw = json.loads(open('C:/Users/dmsak/cnu-llm-bot/data/crawled_staging/sweep_library_cnu_ac_kr.json', encoding='utf-8').read())
print(f"\nsweep_library docs: {len(sw)}")
for d in sw:
    print(f"  url: {d.get('source_url','?')}")

# Try to fetch a few candidate paths
import time
candidates = [
    '/menu/menu.do',
    '/menu/guide.do',
    '/board/list.do',
    '/notice/list.do',
    '/info/hour.do',
    '/mylib/mylib.do',
    '/search/search.do?searchType=SIMPLE',
]
for p in candidates:
    try:
        h2 = fetch_html(f'https://library.cnu.ac.kr{p}', timeout=10)
        txt = extract_main_text(h2, min_len=60)
        print(f"\n  {p}: html={len(h2)}, text={len(txt) if txt else 0}")
        if txt:
            print(f"    snippet: {txt[:120]}")
    except Exception as e:
        print(f"\n  {p}: ERROR {e}")
    time.sleep(0.15)
