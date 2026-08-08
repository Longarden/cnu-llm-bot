"""static2 보강 대상(셔틀/식단/학사일정) 정적 페이지 진입점 탐색.

plus.cnu.ac.kr / www.cnu.ac.kr / mobileadmin.cnu.ac.kr 에서
셔틀/통학버스/학식/식당/학사일정/학사력 키워드 링크를 찾아
실제 본문이 추출되는 정적 페이지 URL을 출력한다.
"""
import sys, re, time
from urllib.parse import urljoin, urlparse
sys.path.insert(0, 'C:/Users/dmsak/cnu-llm-bot')
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

from crawler_pipeline.body_extractor import fetch_html, extract_main_text

SHUTTLE_KW = ['셔틀', '통학', '버스', 'shuttle', 'bus', '노선', '정류장', '시간표']
DINING_KW = ['식당', '식단', '학식', '푸드', '구내식당', 'food', '생활관 식당', '운영시간']
ACAD_KW = ['학사일정', '학사력', '학사안내', '수강신청', '시험', '방학', 'calendar',
           'schedule', '학기', '학사정보']


def probe(url, timeout=12):
    try:
        html = fetch_html(url, timeout=timeout)
    except Exception as e:
        return None, 0, 0, f"ERR:{type(e).__name__}"
    txt = extract_main_text(html, min_len=80)
    tm = re.search(r'<title[^>]*>([^<]+)</title>', html or '')
    title = tm.group(1).strip() if tm else ''
    return html, len(html), len(txt) if txt else 0, title


def find_kw_links(html, base, kws):
    found = {}
    for m in re.finditer(r'<a[^>]+href=["\']([^"\'#]+)["\'][^>]*>(.*?)</a>',
                         html or '', re.DOTALL | re.IGNORECASE):
        href, anchor = m.group(1), re.sub(r'<[^>]+>', '', m.group(2)).strip()
        if href.startswith(('javascript', 'mailto', '#')):
            continue
        full = urljoin(base, href)
        blob = (href + ' ' + anchor).lower()
        if any(k.lower() in blob for k in kws):
            found[full] = anchor[:40]
    return found


print('############ plus.cnu.ac.kr root menu ############', flush=True)
root = 'https://plus.cnu.ac.kr/'
html, hl, tl, title = probe(root, timeout=15)
print(f'root html={hl} text={tl} title={title[:50]}')
for grp, kws in [('SHUTTLE', SHUTTLE_KW), ('DINING', DINING_KW), ('ACAD', ACAD_KW)]:
    links = find_kw_links(html, root, kws)
    print(f'\n  [{grp}] {len(links)} kw-links:')
    for u, a in list(links.items())[:25]:
        print(f'    {a:30s} {u}')

print('\n############ www.cnu.ac.kr root menu ############', flush=True)
for wroot in ['https://www.cnu.ac.kr/', 'https://www.cnu.ac.kr/wwwkor/index.do']:
    html, hl, tl, title = probe(wroot, timeout=15)
    print(f'\n{wroot} html={hl} text={tl} title={title[:50]}')
    if not html:
        continue
    for grp, kws in [('SHUTTLE', SHUTTLE_KW), ('DINING', DINING_KW), ('ACAD', ACAD_KW)]:
        links = find_kw_links(html, wroot, kws)
        if links:
            print(f'  [{grp}] {len(links)}:')
            for u, a in list(links.items())[:15]:
                print(f'    {a:25s} {u}')

print('\n############ known shuttle/dining static probes ############', flush=True)
KNOWN = [
    'https://plus.cnu.ac.kr/html/kr/sub05/sub05_050403.html',  # 셔틀(기존)
    'https://plus.cnu.ac.kr/html/kr/sub05/sub05_0504.html',
    'https://plus.cnu.ac.kr/html/kr/sub05/sub05_050401.html',
    'https://plus.cnu.ac.kr/html/kr/sub05/sub05_050402.html',
    'https://plus.cnu.ac.kr/html/kr/sub05/sub05_0501.html',
    'https://plus.cnu.ac.kr/html/kr/sub05/sub05_0505.html',
    'https://mobileadmin.cnu.ac.kr/food/index.jsp',
    'https://mobileadmin.cnu.ac.kr/food/foodView.jsp',
]
for u in KNOWN:
    html, hl, tl, title = probe(u)
    print(f'  text={tl:5d} html={hl:7d} {title[:35]:35s} {u}')
    time.sleep(0.12)
