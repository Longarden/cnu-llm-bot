"""extra_notices 보강 크롤러 (워커 전용 standalone 스크립트).

목표: 공지(label 1) 보강.
 (a) 비교과/학생지원 통합 공지: cnustudent.cnu.ac.kr 학생처 게시판(살아있는 200 URL).
 (b) in-scope 학과(전자/기계/경영/신소재/수학) 공지 게시판 최신 학사/장학/취업/비교과 공지.

출력: data/crawled_staging/extra_notices.json  (BaseCrawler._make_doc 와 동일한 9키)
실행: py -3.13 scripts/crawl_extra_notices.py

규칙 준수:
 - 충남대(*.cnu.ac.kr)만 크롤.
 - 인코딩은 fetch_html(apparent_encoding 보정)로 처리 → 모지바케/U+FFFD 0건.
 - original_text 30자 이상만 채택.
 - git 작업 없음. 이 staging 파일 1개에만 기록.
"""
import sys, os, json, re
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlparse, parse_qs

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bs4 import BeautifulSoup
from crawler_pipeline.body_extractor import fetch_html, fetch_post
from crawler_pipeline.text_repair import repair_encoding

CATEGORY_ID = "K_notices"
FRESHNESS = "time_sensitive"
OUT_PATH = os.path.join(ROOT, "data", "crawled_staging", "extra_notices.json")

NOW = datetime.utcnow().isoformat()
TODAY = NOW[:10]
VALID = (datetime.utcnow() + timedelta(days=1)).isoformat()

# (목록 URL, 소스라벨)  — 모두 사전 probe로 200 + UTF-8 clean 확인됨.
#  학과는 notices.py가 쓰는 computer 보드와 겹치지 않게 전자/기계/경영/신소재/수학만.
SOURCES = [
    ("https://cnustudent.cnu.ac.kr/cnustudent/community/integ_notice.do", "학생지원_통합공지"),
    ("https://cnustudent.cnu.ac.kr/cnustudent/notice/notice.do", "학생지원_공지"),
    ("https://ee.cnu.ac.kr/ee/community/notice.do", "전자공학과_공지"),
    ("https://biz.cnu.ac.kr/biz/community/notice.do", "경영학부_공지"),
    ("https://math.cnu.ac.kr/math/community/notice.do", "수학과_공지"),
    ("https://me.cnu.ac.kr/me/news/notice01.do", "기계공학부_공지"),
    ("https://mse.cnu.ac.kr/mse/square/notice01.do", "신소재공학과_공지"),
]

SKIP_TITLES = {"다음글", "이전글", "목록", "처음", "이전", "다음", "마지막", "검색", "더보기", "글쓰기", "RSS"}
# 학부생 비대상(대학원/교원 전용) 위주 제외 키워드.
GRAD_ONLY = ("대학원", "학위청구", "학위논문", "박사", "석사학위", "BK21", "교수초빙", "전임교원")
# 학부생 우선순위 키워드(학사/장학/취업/비교과). 동일 날짜 내 우선.
PRIORITY_KW = ("학사", "장학", "비교과", "수강", "졸업", "등록금", "학자금", "근로", "현장실습",
               "인턴", "취업", "채용", "공모", "모집", "교환학생", "복수전공", "성적", "휴학",
               "복학", "역량", "프로그램", "특강", "세미나", "경진")

DATE_RE = re.compile(r"(\d{2,4})[-.](\d{1,2})[-.](\d{1,2})")


def parse_date(text: str) -> str:
    """문자열에서 날짜 1개를 뽑아 YYYY-MM-DD 로 정규화. 미래/비정상은 버림."""
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
    if dt > datetime.utcnow() + timedelta(days=2):
        return ""
    if dt.year < 2015:
        return ""
    return dt.strftime("%Y-%m-%d")


def row_date(row) -> str:
    """테이블 행 셀에서 날짜 추출(조회수/번호 칸 오인 방지: 셀 전체가 날짜인 칸 우선)."""
    cells = row.find_all("td")
    for td in cells:
        t = td.get_text(strip=True)
        if DATE_RE.fullmatch(t):
            return parse_date(t)
    dt_tag = row.select_one("td.date, .date, td.b-td-date")
    if dt_tag:
        d = parse_date(dt_tag.get_text(strip=True))
        if d:
            return d
    for td in cells:
        d = parse_date(td.get_text(strip=True))
        if d:
            return d
    return ""


def collect_table(soup, list_url):
    """jwxe 계열 학과 게시판(table tbody tr). [(title, link, date_hint), ...]"""
    out = []
    for row in soup.select("table tbody tr"):
        a = row.select_one("td.subject a, td.title a, td.b-td-left a, td a")
        if not a:
            continue
        title = repair_encoding(a.get_text(strip=True))
        if not title or len(title) < 3 or title in SKIP_TITLES:
            continue
        href = a.get("href", "")
        if not href or href.startswith("#") or href.lower().startswith("javascript"):
            continue
        link = urljoin(list_url, href)
        out.append((title, link, row_date(row)))
    return out


def collect_cards(soup, list_url):
    """cnustudent 카드형 보드(a?mode=view&articleNo=...). [(title, link, date_hint), ...]"""
    out = []
    seen = set()
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        if "mode=view" not in href or "articleNo" not in href:
            continue
        qs = parse_qs(urlparse(href).query)
        art = qs.get("articleNo", [""])[0]
        title = repair_encoding(a.get_text(strip=True))
        if not title or len(title) < 5 or title in SKIP_TITLES:
            continue
        key = art or href
        if key in seen:
            continue
        seen.add(key)
        out.append((title, urljoin(list_url, href), ""))
    return out


def make_doc(title, content, source_url, date):
    title = repair_encoding(title)
    content = repair_encoding(content)
    return {
        "source_url": source_url,
        "data_category": CATEGORY_ID,
        "last_crawled_at": NOW,
        "valid_until": VALID,
        "freshness_tier": FRESHNESS,
        "original_text": content,
        "title": title,
        "content": content,
        "date": date or TODAY,
    }


def main():
    items = []
    seen_links = set()
    per_source_cap = 12  # 각 게시판 최신 5~10건 이상 확보 후 정렬, 소스당 상한.
    for list_url, label in SOURCES:
        try:
            html = fetch_html(list_url, timeout=25)
        except Exception as e:
            print(f"[skip] {label} 목록 실패: {type(e).__name__}: {e}")
            continue
        soup = BeautifulSoup(html, "html.parser")
        rows = collect_table(soup, list_url)
        if not rows:
            rows = collect_cards(soup, list_url)
        if not rows:
            print(f"[warn] {label}: 행 0건 (셀렉터 불일치) {list_url}")
            continue

        kept = 0
        for title, link, date_hint in rows:
            if kept >= per_source_cap:
                break
            if link in seen_links:
                continue
            if any(g in title for g in GRAD_ONLY):
                continue  # 대학원/교원 전용 제외(학부생 대상 위주)
            seen_links.add(link)
            post = fetch_post(link, timeout=20, min_len=20)
            if post and post.get("text"):
                body = repair_encoding(post["text"])
                content = body if title in body else f"{title}\n\n{body}"
                date = date_hint or parse_date(post.get("date", "")) or parse_date(body)
            else:
                content = title
                date = date_hint
            if len(content) < 30:
                # original_text 30자 미만이면 제목을 보강해 본문 구성, 그래도 부족하면 스킵
                content = f"[{label}] {title}"
                if len(content) < 30:
                    continue
            items.append(make_doc(title, content, link, date))
            kept += 1
        print(f"[ok] {label}: {kept}건 (후보 {len(rows)})")

    # 최신순 + 학부생 우선 키워드 가산(동일 날짜 내)
    def sort_key(doc):
        prio = 1 if any(k in doc["title"] for k in PRIORITY_KW) else 0
        return (doc.get("date", ""), prio)

    items.sort(key=sort_key, reverse=True)

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

    # 자체 검증 리포트
    blob = json.dumps(items, ensure_ascii=False)
    ufffd = blob.count("�")
    short = sum(1 for d in items if len(d["original_text"]) < 30)
    print("=" * 60)
    print(f"WROTE {OUT_PATH}")
    print(f"count={len(items)}  U+FFFD={ufffd}  original_text<30={short}")
    print("sample titles (newest-first):")
    for d in items[:8]:
        print(f"  {d['date']} | {d['title'][:55]}")


if __name__ == "__main__":
    main()
