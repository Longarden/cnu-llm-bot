"""plus.cnu.ac.kr 메인 메뉴에서 장학/식당 링크 찾기."""
import sys, re, time
sys.path.insert(0, 'C:/Users/dmsak/cnu-llm-bot')
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

from crawler_pipeline.body_extractor import fetch_html, extract_main_text

html = fetch_html('https://plus.cnu.ac.kr/', timeout=15)
print(f"html size: {len(html)}")

# Find all .html links
all_links = re.findall(r'href=["\']([^"\']+\.html)["\']', html)
print(f"Total .html links: {len(all_links)}")

# Group by sub path
from collections import defaultdict
by_sub = defaultdict(list)
for l in all_links:
    m = re.search(r'/(sub\d+)/', l)
    if m:
        by_sub[m.group(1)].append(l)
    else:
        by_sub['other'].append(l)

for sub, links in sorted(by_sub.items()):
    print(f"\n  {sub} ({len(links)} links):")
    for l in sorted(set(links))[:20]:
        print(f"    {l}")

# Find text near 장학 (scholarship) keyword
import re
sch_ctx = re.findall(r'.{0,50}장학.{0,100}', html)
print(f"\n=== 장학 contexts ({len(sch_ctx)}) ===")
for c in sch_ctx[:15]:
    print(f"  {c.strip()}")

# Find text near 식당/식단 (dining) keyword
din_ctx = re.findall(r'.{0,50}(?:식당|식단|학식).{0,100}', html)
print(f"\n=== 식당/식단 contexts ({len(din_ctx)}) ===")
for c in din_ctx[:10]:
    print(f"  {c.strip()}")

# probe sub03 index
print("\n=== sub03 index ===")
for path in ['/html/kr/sub03/', '/html/kr/sub03/sub03_0301.html',
             '/html/kr/sub03/sub03_030101.html', '/html/kr/sub03/sub03_0302.html',
             '/html/kr/sub03/sub03_030201.html']:
    try:
        h = fetch_html(f'https://plus.cnu.ac.kr{path}', timeout=10)
        t = extract_main_text(h, min_len=60)
        tm = re.search(r'<title[^>]*>([^<]+)</title>', h)
        print(f"  {path}: html={len(h)} text={len(t) if t else 0} title={tm.group(1).strip() if tm else ''}")
        if t and len(t) > 100:
            print(f"    snippet: {t[:150]}")
    except Exception as e:
        print(f"  {path}: ERR {e}")
    time.sleep(0.12)
