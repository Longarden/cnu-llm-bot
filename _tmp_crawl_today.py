"""One-shot staging crawl: latest school/department notices -> today_notices.json.
Reuses repo fetchers (crawler_pipeline.body_extractor) and notices.py date logic.
"""
import re
import json
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from crawler_pipeline.body_extractor import fetch_html, fetch_body

NOW_ISO = datetime.now().isoformat()
TODAY = "2026-06-09"
VALID_UNTIL = "2026-09-30T00:00:00"

SOURCES = [
    ("https://plus.cnu.ac.kr/_prog/_board/?code=sub07_0701&mode=list", "교내 일반소식"),
    ("https://plus.cnu.ac.kr/_prog/_board/?code=sub07_0702&mode=list", "취업/장학/행사"),
    ("https://computer.cnu.ac.kr/computer/notice/notice.do", "학부 공지"),
    ("https://computer.cnu.ac.kr/computer/notice/bachelor.do", "학사 공지"),
    ("https://computer.cnu.ac.kr/computer/notice/project.do", "프로젝트 공지"),
]

SKIP_TITLES = {"다음글", "이전글", "목록", "처음", "이전", "다음", "마지막",
               "검색", "더보기", "글쓰기", "RSS", "공지", "첨부파일"}
DATE_RE = re.compile(r"(\d{2,4})[-.](\d{1,2})[-.](\d{1,2})")


def parse_date(text):
    if not text:
        return ""
    m = DATE_RE.search(text)
    if not m:
        return ""
    y, mo, d = m.group(1), m.group(2), m.group(3)
    if len(y) == 2:
        y = "20" + y
    try:
        dt = datetime(int(y), int(mo), int(d))
    except ValueError:
        return ""
    if dt > datetime(2026, 6, 11):  # future-parse guard (today + 2d)
        return ""
    return dt.strftime("%Y-%m-%d")


def row_date(row):
    cells = row.find_all("td")
    for td in cells:
        t = td.get_text(strip=True)
        if DATE_RE.fullmatch(t):
            d = parse_date(t)
            if d:
                return d
    dt_tag = row.select_one("td.date, .date")
    if dt_tag:
        d = parse_date(dt_tag.get_text(strip=True))
        if d:
            return d
    for td in cells:
        d = parse_date(td.get_text(strip=True))
        if d:
            return d
    return ""


def clean(s):
    return s.replace("�", "") if s else s


records = []
seen = set()
worked = []

for url, label in SOURCES:
    try:
        html = fetch_html(url, timeout=25)
        soup = BeautifulSoup(html, "html.parser")
    except Exception as e:
        print(f"[skip] {url} -> {e}")
        continue

    rows = soup.select("tr, .board-list li")
    got_from_src = 0
    for row in rows[:40]:
        title_tag = row.select_one("td.subject a, .tit a, .title a, td a")
        if not title_tag:
            continue
        title = title_tag.get_text(strip=True)
        if not title or len(title) < 3 or title in SKIP_TITLES:
            continue
        href = title_tag.get("href", "")
        link = urljoin(url, href) if href else ""
        if not link or "�" in link:
            continue
        if link in seen:
            continue
        date_str = row_date(row)

        body = fetch_body(link, timeout=20, min_len=20)
        if not body:
            continue
        body = clean(body).strip()
        if "�" in (title + body):
            continue
        if len(body) < 20:
            continue
        if not date_str:
            date_str = parse_date(body)
        date_str = date_str or TODAY

        full = f"{title}\n\n{body}".strip()
        if "�" in full:
            continue

        seen.add(link)
        records.append({
            "source_url": link,
            "data_category": "K_notices",
            "last_crawled_at": NOW_ISO,
            "valid_until": VALID_UNTIL,
            "freshness_tier": "time_sensitive",
            "original_text": full,
            "title": clean(title),
            "content": full,
            "date": date_str,
        })
        got_from_src += 1
        if got_from_src >= 14:  # cap per source
            break

    if got_from_src:
        worked.append(f"{label} ({got_from_src})")
    print(f"[src] {url} -> {got_from_src} records")

# sort newest first by date
records.sort(key=lambda r: r["date"], reverse=True)

out = r"C:\Users\dmsak\cnu-llm-bot\data\crawled_staging\today_notices.json"
with open(out, "w", encoding="utf-8") as f:
    json.dump(records, f, ensure_ascii=False, indent=2)

print("=" * 50)
print(f"TOTAL WRITTEN: {len(records)}")
print("SOURCES WORKED:", "; ".join(worked) if worked else "none")
print("SAMPLES:")
for r in records[:3]:
    print(f"  - {r['date']} | {r['title'][:60]}")
