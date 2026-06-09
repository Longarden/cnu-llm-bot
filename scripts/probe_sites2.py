"""2차 프로브 - library 실제 경로 + plus scholarship/dining sub 구조."""
import sys, re, time
sys.path.insert(0, 'C:/Users/dmsak/cnu-llm-bot')
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

from crawler_pipeline.body_extractor import fetch_html, extract_main_text

def probe_text(label, url):
    print(f"\n=== {label}: {url} ===")
    try:
        html = fetch_html(url, timeout=15)
    except Exception as e:
        print(f"  ERROR: {e}")
        return None, ''
    text = extract_main_text(html, min_len=80)
    print(f"  html={len(html)}  text={'(none)' if not text else len(text)}")
    if text:
        print(f"  snippet: {text[:200]}")
    # find sub-links
    links = re.findall(r'href=["\']([^"\'#\s]+\.(?:do|html|jsp))["\']', html)
    return text, links

# Library: try known pattern paths
lib_paths = [
    '/util/service.do',
    '/util/info.do',
    '/service/guide.do',
    '/service/intro.do',
    '/guide/guide.do',
    '/guide/service.do',
    '/info/info.do',
    '/loan/loan.do',
    '/space/space.do',
    '/user/user.do',
    '/search/search.do',
]
for p in lib_paths:
    _, _ = probe_text(f"library{p}", f"https://library.cnu.ac.kr{p}")
    time.sleep(0.15)

# Plus: scan sub05 pages (dining, shuttle, etc)
print("\n\n=== PLUS sub05 scan ===")
plus_sub5 = [
    '/html/kr/sub05/sub05_050101.html',  # 학생생활 서비스
    '/html/kr/sub05/sub05_050201.html',
    '/html/kr/sub05/sub05_050301.html',  # dining
    '/html/kr/sub05/sub05_050401.html',
    '/html/kr/sub05/sub05_050402.html',
    '/html/kr/sub05/sub05_050403.html',  # shuttle
    '/html/kr/sub05/sub05_050404.html',
    '/html/kr/sub05/sub05_050501.html',
]
for p in plus_sub5:
    _, links = probe_text(f"plus{p}", f"https://plus.cnu.ac.kr{p}")
    time.sleep(0.15)

# Plus: scholarship sub04
print("\n\n=== PLUS sub04 scan ===")
plus_sub4 = [
    '/html/kr/sub04/sub04_040201.html',
    '/html/kr/sub04/sub04_040301.html',
    '/html/kr/sub04/sub04_0401.html',
    '/html/kr/sub04/sub04_0402.html',
    '/html/kr/sub04/sub04_0403.html',
    '/html/kr/sub04/sub04_0404.html',
    '/html/kr/sub04/sub04_040101.html',
]
for p in plus_sub4:
    _, links = probe_text(f"plus{p}", f"https://plus.cnu.ac.kr{p}")
    time.sleep(0.15)

# cnustudent specific pages
print("\n\n=== cnustudent pages ===")
cnu_pages = [
    '/cnustudent/notice/bus_route.do',
    '/cnustudent/notice/cooperation.do',
    '/cnustudent/notice/cooper_food.do',
    '/cnustudent/notice/facilities.do',
    '/cnustudent/notice/notice.do',
    '/cnustudent/notice/calendar.do',
    '/cnustudent/community/integ_notice.do',
]
for p in cnu_pages:
    _, _ = probe_text(f"cnustudent{p}", f"https://cnustudent.cnu.ac.kr{p}")
    time.sleep(0.15)
