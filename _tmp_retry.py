"""Retry the two sources that hit ConnectionReset, merge into today_notices.json."""
import re, json, time
from datetime import datetime
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from crawler_pipeline.body_extractor import fetch_html, fetch_body

OUT = r"C:\Users\dmsak\cnu-llm-bot\data\crawled_staging\today_notices.json"
NOW_ISO = datetime.now().isoformat()
TODAY = "2026-06-09"
VALID_UNTIL = "2026-09-30T00:00:00"
DATE_RE = re.compile(r"(\d{2,4})[-.](\d{1,2})[-.](\d{1,2})")
SKIP = {"다음글","이전글","목록","처음","이전","다음","마지막","검색","더보기","글쓰기","RSS","공지","첨부파일"}
RETRY = [
    ("https://plus.cnu.ac.kr/_prog/_board/?code=sub07_0701&mode=list", "교내 일반소식"),
    ("https://computer.cnu.ac.kr/computer/notice/notice.do", "학부 공지"),
]

def parse_date(t):
    if not t: return ""
    m=DATE_RE.search(t)
    if not m: return ""
    y,mo,d=m.group(1),m.group(2),m.group(3)
    if len(y)==2: y="20"+y
    try: dt=datetime(int(y),int(mo),int(d))
    except ValueError: return ""
    if dt>datetime(2026,6,11): return ""
    return dt.strftime("%Y-%m-%d")

def row_date(row):
    cells=row.find_all("td")
    for td in cells:
        t=td.get_text(strip=True)
        if DATE_RE.fullmatch(t):
            d=parse_date(t)
            if d: return d
    for td in cells:
        d=parse_date(td.get_text(strip=True))
        if d: return d
    return ""

records=json.load(open(OUT,encoding="utf-8"))
seen={r["source_url"] for r in records}
added=0
for url,label in RETRY:
    html=None
    for attempt in range(4):
        try:
            html=fetch_html(url,timeout=30); break
        except Exception as e:
            print(f"[try{attempt}] {url} -> {e}"); time.sleep(2)
    if not html:
        print(f"[give-up] {url}"); continue
    soup=BeautifulSoup(html,"html.parser")
    got=0
    for row in soup.select("tr, .board-list li")[:40]:
        tt=row.select_one("td.subject a, .tit a, .title a, td a")
        if not tt: continue
        title=tt.get_text(strip=True)
        if not title or len(title)<3 or title in SKIP: continue
        href=tt.get("href",""); link=urljoin(url,href) if href else ""
        if not link or "�" in link or link in seen: continue
        ds=row_date(row)
        body=fetch_body(link,timeout=20,min_len=20)
        if not body: continue
        body=body.replace("�","").strip()
        if len(body)<20: continue
        if not ds: ds=parse_date(body)
        ds=ds or TODAY
        full=f"{title}\n\n{body}".strip()
        if "�" in full: continue
        seen.add(link)
        records.append({"source_url":link,"data_category":"K_notices","last_crawled_at":NOW_ISO,
            "valid_until":VALID_UNTIL,"freshness_tier":"time_sensitive","original_text":full,
            "title":title.replace("�",""),"content":full,"date":ds})
        got+=1; added+=1
        if got>=12: break
    print(f"[src] {url} -> {got}")

records.sort(key=lambda r:r["date"],reverse=True)
json.dump(records,open(OUT,"w",encoding="utf-8"),ensure_ascii=False,indent=2)
print("ADDED",added,"TOTAL",len(records))
