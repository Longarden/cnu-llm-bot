"""사이트 탐색 프로브 - 진입점 파악용."""
import sys, re
sys.path.insert(0, 'C:/Users/dmsak/cnu-llm-bot')
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

from crawler_pipeline.body_extractor import fetch_html

def probe(label, url, domain_filter=None):
    print(f"\n=== {label}: {url} ===")
    try:
        html = fetch_html(url, timeout=15)
    except Exception as e:
        print(f"  ERROR: {e}")
        return
    print(f"  html size: {len(html)}")
    tm = re.search(r'<title[^>]*>([^<]+)</title>', html)
    print(f"  title: {tm.group(1).strip() if tm else 'none'}")
    # collect all .do and .html links
    links = set()
    for href in re.findall(r'href=["\']([^"\'#\s]+)["\']', html):
        if domain_filter and domain_filter not in href and not href.startswith('/'):
            continue
        if href.startswith('/') or domain_filter in href if domain_filter else True:
            links.add(href)
    do_html = [l for l in links if '.do' in l or '.html' in l or '.jsp' in l]
    print(f"  total links: {len(links)}, .do/.html/.jsp: {len(do_html)}")
    for l in sorted(do_html)[:30]:
        print(f"    {l}")

# 1. library.cnu.ac.kr
probe("library root", "https://library.cnu.ac.kr/", "library.cnu.ac.kr")
probe("library content", "https://library.cnu.ac.kr/content/menu.do", "library.cnu.ac.kr")
probe("library intro", "https://library.cnu.ac.kr/intro/intro.do", "library.cnu.ac.kr")
probe("library service", "https://library.cnu.ac.kr/service/service.do", "library.cnu.ac.kr")
probe("library guide loan", "https://library.cnu.ac.kr/guide/loan.do", "library.cnu.ac.kr")

# 2. shuttle
probe("plus shuttle", "https://plus.cnu.ac.kr/html/kr/sub05/sub05_050403.html", "plus.cnu.ac.kr")

# 3. dining
probe("mobileadmin food", "https://mobileadmin.cnu.ac.kr/food/index.jsp", "mobileadmin.cnu.ac.kr")
probe("plus dining", "https://plus.cnu.ac.kr/html/kr/sub05/sub05_050301.html", "plus.cnu.ac.kr")

# 4. scholarship
probe("plus scholarship", "https://plus.cnu.ac.kr/html/kr/sub04/sub04_040101.html", "plus.cnu.ac.kr")

# 5. cnustudent
probe("cnustudent root", "https://cnustudent.cnu.ac.kr/", "cnustudent.cnu.ac.kr")
probe("cnustudent index", "https://cnustudent.cnu.ac.kr/index.do", "cnustudent.cnu.ac.kr")
