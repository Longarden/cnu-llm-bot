"""static2 2차 탐색: 학사안내 페이지 형제 링크 + sub05 메뉴 구조 + 식당 안내 페이지."""
import sys, re, time
from urllib.parse import urljoin
sys.path.insert(0, 'C:/Users/dmsak/cnu-llm-bot')
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

from crawler_pipeline.body_extractor import fetch_html, extract_main_text


def probe(url, timeout=12):
    try:
        html = fetch_html(url, timeout=timeout)
    except Exception as e:
        return None, 0, 0, f"ERR:{type(e).__name__}"
    txt = extract_main_text(html, min_len=60)
    tm = re.search(r'<title[^>]*>([^<]+)</title>', html or '')
    return html, len(html), len(txt) if txt else 0, (tm.group(1).strip() if tm else '')


def sibling_html_links(html, base):
    out = {}
    for m in re.finditer(r'<a[^>]+href=["\']([^"\'#]+\.html)["\'][^>]*>(.*?)</a>',
                         html or '', re.DOTALL | re.IGNORECASE):
        href = m.group(1)
        anchor = re.sub(r'<[^>]+>', '', m.group(2)).strip()
        full = urljoin(base, href)
        if 'plus.cnu.ac.kr/html/kr' in full:
            out[full] = anchor[:35]
    return out


print('===== 학사안내 sub05_05020101 형제 메뉴 =====', flush=True)
acad = 'https://plus.cnu.ac.kr/html/kr/sub05/sub05_05020101.html'
html, hl, tl, title = probe(acad, timeout=15)
print(f'학사안내 text={tl} title={title[:40]}')
if html:
    sibs = sibling_html_links(html, acad)
    print(f'  {len(sibs)} sub05 .html links:')
    for u, a in sorted(sibs.items()):
        short = u.replace('https://plus.cnu.ac.kr/html/kr/', '')
        print(f'    {short:30s} {a}')

print('\n===== 학사안내 본문 학사/수강/시험 형제 페이지 직접 probe =====', flush=True)
# sub05_0502YY: 학사 관련 (학사안내=05020101)
cands = []
for yy in range(1, 9):
    for zz in range(1, 6):
        cands.append(f'sub05_0502{yy:02d}{zz:02d}')
# 정리: 패턴이 05020101 형태(8자리). 05 02 01 01
cands = [f'sub05_0502{a:02d}{b:02d}' for a in range(1, 9) for b in range(1, 5)]
seen_text = {}
for c in cands:
    u = f'https://plus.cnu.ac.kr/html/kr/sub05/{c}.html'
    html, hl, tl, title = probe(u)
    if tl > 200 and title and '충남대학교' != title.strip():
        print(f'  text={tl:5d} {title[:45]:45s} {c}')
    time.sleep(0.07)

print('\n===== 셔틀 본문 미리보기 =====', flush=True)
html, hl, tl, title = probe('https://plus.cnu.ac.kr/html/kr/sub05/sub05_050403.html', timeout=15)
txt = extract_main_text(html, min_len=60)
print((txt or '')[:600])

print('\n===== 식당(food) index 본문 + 식당안내 페이지 =====', flush=True)
for u in ['https://mobileadmin.cnu.ac.kr/food/index.jsp',
          'https://mobileadmin.cnu.ac.kr/food/',
          'https://mobileadmin.cnu.ac.kr/food/foodInfo.jsp',
          'https://mobileadmin.cnu.ac.kr/food/info.jsp']:
    html, hl, tl, title = probe(u)
    print(f'  text={tl:5d} html={hl:7d} {title[:30]:30s} {u}')
    if html and tl > 100:
        txt = extract_main_text(html, min_len=60)
        print('    >>', (txt or '')[:250].replace(chr(10), ' '))
    time.sleep(0.1)

print('\n===== 생활관/학생회관 식당 안내 (dorm) =====', flush=True)
for u in ['https://dorm.cnu.ac.kr/html/kr/',
          'https://plus.cnu.ac.kr/html/kr/sub05/sub05_050401.html']:
    html, hl, tl, title = probe(u, timeout=15)
    print(f'  text={tl:5d} {title[:35]:35s} {u}')
    time.sleep(0.1)
