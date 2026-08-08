"""plus.cnu.ac.kr 전체 sub 구조 탐색 + scholarship 위치 파악."""
import sys, re, time
sys.path.insert(0, 'C:/Users/dmsak/cnu-llm-bot')
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

from crawler_pipeline.body_extractor import fetch_html, extract_main_text

def probe(url):
    try:
        html = fetch_html(url, timeout=12)
        txt = extract_main_text(html, min_len=80)
        tm = re.search(r'<title[^>]*>([^<]+)</title>', html)
        title = tm.group(1).strip() if tm else ''
        return len(html), len(txt) if txt else 0, title
    except Exception as e:
        return 0, 0, f"ERR:{e}"

# scan sub01~sub06, pages 01-06
base = 'https://plus.cnu.ac.kr/html/kr'
print("sub / path / html_size / text_len / title")
for s in ['sub01','sub02','sub03','sub04','sub05','sub06']:
    for p in range(1, 7):
        for sp in range(1, 8):
            path = f'/{s}/{s}_0{p}0{sp}01.html'
            url = base + path
            hlen, tlen, title = probe(url)
            if hlen > 0 and tlen > 100:
                print(f"  {path}: html={hlen} text={tlen} title={title[:60]}")
            time.sleep(0.08)

# specifically check scholarship-related paths
print("\n=== Scholarship sub03 ===")
for sub in ['sub03_030101','sub03_030201','sub03_030301','sub03_030401',
            'sub03_030102','sub03_030103']:
    path = f'/sub03/{sub}.html'
    hlen, tlen, title = probe(base + path)
    print(f"  {path}: html={hlen} text={tlen} title={title[:80]}")
    time.sleep(0.1)
