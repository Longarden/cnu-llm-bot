"""static2 3차: 학사일정 월별 + 교육과정 페이지 본문 + 생활관 식당 안내 확인."""
import sys, re, time
from urllib.parse import urljoin
sys.path.insert(0, 'C:/Users/dmsak/cnu-llm-bot')
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
from crawler_pipeline.body_extractor import fetch_html, extract_main_text


def probe(url, timeout=12, ml=60):
    try:
        html = fetch_html(url, timeout=timeout)
    except Exception as e:
        return None, 0, f"ERR:{type(e).__name__}"
    txt = extract_main_text(html, min_len=ml)
    return html, len(txt) if txt else 0, (txt or '')


print('===== 학사일정 academic_calendar (월별) =====', flush=True)
cal = 'https://plus.cnu.ac.kr/_prog/academic_calendar/?site_dvs_cd=kr&menu_dvs_cd=05020101'
html, tl, txt = probe(cal, timeout=15, ml=40)
print(f'calendar text={tl}')
print(txt[:700])

print('\n===== 학사일정 월별 sub05_05020101_NN =====', flush=True)
for mm in range(1, 13):
    u = f'https://plus.cnu.ac.kr/html/kr/sub05/sub05_05020101_{mm:02d}.html'
    html, tl, txt = probe(u)
    print(f'  {mm:02d}월 text={tl:5d}  {txt[:60].strip()}')
    time.sleep(0.07)

print('\n===== 교육과정/졸업 페이지 (sub05_0512XX) =====', flush=True)
curr = {
    'sub05_051201': '교육과정해설', 'sub05_051202': '졸업이수학점',
    'sub05_051204': '전공과정', 'sub05_051205': '융복합창의전공',
    'sub05_051206': '복수전공', 'sub05_051207': '부전공',
    'sub05_051208': '교직과정', 'sub05_051209': '평생교육사',
    'sub05_050202': '학사업무안내', 'sub05_05020103': '전문대학원특수대학원일정',
}
for c, name in curr.items():
    u = f'https://plus.cnu.ac.kr/html/kr/sub05/{c}.html'
    html, tl, txt = probe(u)
    print(f'  text={tl:5d} {name:20s} {c}  | {txt[:50].strip()}')
    time.sleep(0.08)

print('\n===== 셔틀 관련 보조 (주차/기타서비스) =====', flush=True)
for c, name in [('sub05_05040201', '주차안내'), ('sub05_050404', '기타서비스안내')]:
    u = f'https://plus.cnu.ac.kr/html/kr/sub05/{c}.html'
    html, tl, txt = probe(u)
    print(f'  text={tl:5d} {name:14s} {c} | {txt[:60].strip()}')
    time.sleep(0.08)

print('\n===== 생활관 식당 안내 (dorm) =====', flush=True)
droot = 'https://dorm.cnu.ac.kr/html/kr/'
html, tl, txt = probe(droot, timeout=15)
links = {}
for m in re.finditer(r'<a[^>]+href=["\']([^"\'#]+\.html)["\'][^>]*>(.*?)</a>',
                     html or '', re.DOTALL | re.IGNORECASE):
    anchor = re.sub(r'<[^>]+>', '', m.group(2)).strip()
    if any(k in (m.group(1)+anchor) for k in ['식당', '식단', 'meal', 'food', '급식', '운영', '시설']):
        links[urljoin(droot, m.group(1))] = anchor[:30]
print(f'  dorm 식당/식단 후보 {len(links)}:')
for u, a in list(links.items())[:15]:
    print(f'    {a:25s} {u}')
