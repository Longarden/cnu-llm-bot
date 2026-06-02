"""컴퓨터인공지능학부(computer.cnu.ac.kr) 학부 졸업요건/교육과정 상세 크롤러.

대상(학부=undergrad 한정, 대학원 /grad/ 전면 제외):
  - 학부소개/교육목표 등 정적 안내 페이지 (/computer/intro/*, B_academic·F_department)
  - 교육 메뉴 정적 페이지 (/computer/edu/{curriculum,requirements,admission01,system20XX})
  - 졸업요건 게시판(/computer/edu/requirements.do) 목록 -> 각 게시글 상세 본문
    (?mode=view&articleNo=...) : 졸업에 관한 학과 규정·트랙/학점 안내 실제 본문

본문 추출: crawler_pipeline.body_extractor.extract_main_text (trafilatura -> BS4 폴백),
인코딩 보정: text_repair.repair_encoding (한국어 mojibake 차단).

출력: data/crawled_staging/cai_gradreq.json
  레코드는 BaseCrawler._make_doc 과 동일한 9키 구조
  (source_url, data_category, last_crawled_at, valid_until, freshness_tier,
   original_text, title, content, date).
나중에 메인이 integrate_verify 로 통합.

검증/안전:
  - 네트워크는 충남대(cnu.ac.kr)만.
  - 타임아웃 30초 + 재시도 2회 (computer.cnu 단발 ReadTimeout 잦음).
  - 본문 부실(<min_len)·중복(source_url) 레코드는 제외.
  - 실패해도 부분 결과를 저장하고 리포트에 사유 남김.
"""

from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin

import requests

# Windows 콘솔 cp949 출력 깨짐 회피 (추출 텍스트 자체는 정상, 표시만 보정)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path("C:/Users/dmsak/cnu-llm-bot")
sys.path.insert(0, str(ROOT))

from crawler_pipeline.body_extractor import extract_main_text  # noqa: E402
from crawler_pipeline.text_repair import repair_encoding  # noqa: E402

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

BASE = "https://computer.cnu.ac.kr"
ALLOWED_HOST_SUFFIX = "cnu.ac.kr"  # 충남대 사이트만 허용

NOW = datetime.now()
LAST_CRAWLED = NOW.isoformat()
VALID_UNTIL = (NOW + timedelta(days=90)).isoformat()
FRESHNESS = "semi_static"

OUT_PATH = ROOT / "data" / "crawled_staging" / "cai_gradreq.json"
REPORT_PATH = OUT_PATH.with_name("cai_gradreq.report.json")

MIN_LEN = 60  # 본문 최소 길이

# 정적 학부 페이지: (path, data_category)
#   교육과정/졸업요건/이수체계 = B_academic, 학부소개/진로 = F_department
STATIC_PAGES: list[tuple[str, str]] = [
    ("/computer/intro/objective.do", "F_department"),   # 교육목표/세부전공
    ("/computer/intro/greeting.do", "F_department"),     # 학부 소개(인사말)
    ("/computer/intro/career.do", "F_department"),       # 졸업 후 진로
    ("/computer/edu/curriculum.do", "B_academic"),       # 교과과정(교과목 표)
    ("/computer/edu/requirements.do", "B_academic"),     # 졸업요건 게시판 목록
    ("/computer/edu/admission01.do", "B_academic"),      # 입학(수시) 안내
]

# 교과목 이수체계도: 페이지 본문은 연도-링크 네비 목록(~292b)이라 연도별로
# 사실상 동일(이미지/도식 기반). 노이즈/중복을 막기 위해 최신 학번 1개만 유지하고,
# 본문 정규화 후 중복이면 추가 제외(dedup_by_content)한다.
SYSTEM_YEARS = [2026]

# 졸업요건 게시판
REQ_BOARD_URL = f"{BASE}/computer/edu/requirements.do"


def is_allowed(url: str) -> bool:
    """충남대 호스트만 허용."""
    try:
        host = re.sub(r"^https?://", "", url).split("/")[0].split(":")[0]
    except Exception:
        return False
    return host.endswith(ALLOWED_HOST_SUFFIX)


def safe_get(url: str, timeout: int = 30, retries: int = 2) -> str | None:
    """GET -> 인코딩 보정된 본문 텍스트. 실패 시 None.

    computer.cnu 가 charset 헤더를 안 주거나 latin1로 잡히는 경우가 있어
    apparent_encoding 으로 보정한다(한국어 깨짐 방지).
    """
    if not is_allowed(url):
        print(f"  [SKIP] 비충남대 URL: {url}")
        return None
    last = None
    for _ in range(retries + 1):
        try:
            r = requests.get(url, headers=HEADERS, timeout=timeout)
            if r.status_code == 200 and r.text:
                enc = (r.encoding or "").lower()
                if not enc or enc in ("iso-8859-1", "latin-1", "ascii"):
                    r.encoding = r.apparent_encoding or r.encoding
                return r.text
            last = f"status={r.status_code}"
        except Exception as e:
            last = str(e)[:80]
            time.sleep(0.7)
    print(f"  [WARN] safe_get fail {url}: {last}")
    return None


def make_doc(source_url: str, title: str, text: str, category: str) -> dict:
    """BaseCrawler._make_doc 와 동일한 9키 구조 문서."""
    text = repair_encoding(text.strip())
    title = repair_encoding(title.strip())
    return {
        "source_url": source_url,
        "data_category": category,
        "last_crawled_at": LAST_CRAWLED,
        "valid_until": VALID_UNTIL,
        "freshness_tier": FRESHNESS,
        "original_text": text,
        "title": title,
        "content": text,
        "date": NOW.strftime("%Y-%m-%d"),
    }


def page_title(html: str, fallback: str) -> str:
    tm = re.search(r"<title[^>]*>([^<]+)</title>", html)
    if tm:
        t = repair_encoding(tm.group(1).strip())
        # "컴퓨터인공지능학부 | 교육 | 교과과정" 형태 → 그대로 사용
        if t:
            return t
    return fallback


def crawl_static(report: list[dict]) -> list[dict]:
    """정적 학부 페이지 본문 수집."""
    docs: list[dict] = []
    for path, cat in STATIC_PAGES:
        url = urljoin(BASE, path)
        html = safe_get(url)
        if not html:
            report.append({"url": url, "kind": "static", "status": "fetch_fail"})
            continue
        body = extract_main_text(html, min_len=MIN_LEN)
        if not body or len(body) < MIN_LEN:
            report.append({"url": url, "kind": "static", "status": "no_body",
                           "len": len(body) if body else 0})
            continue
        title = page_title(html, path)
        docs.append(make_doc(url, title, body, cat))
        report.append({"url": url, "kind": "static", "status": "ok", "len": len(body)})
        print(f"  [static] OK {len(body):5d}b - {title[:50]}")
        time.sleep(0.2)
    return docs


def crawl_system(report: list[dict]) -> list[dict]:
    """교과목 이수체계도(최근 연도) 수집."""
    docs: list[dict] = []
    for year in SYSTEM_YEARS:
        url = f"{BASE}/computer/edu/system{year}.do"
        html = safe_get(url)
        if not html:
            report.append({"url": url, "kind": "system", "status": "fetch_fail"})
            continue
        body = extract_main_text(html, min_len=MIN_LEN)
        if not body or len(body) < MIN_LEN:
            report.append({"url": url, "kind": "system", "status": "no_body",
                           "len": len(body) if body else 0})
            continue
        title = page_title(html, f"{year} 교과목이수체계도")
        docs.append(make_doc(url, title, body, "B_academic"))
        report.append({"url": url, "kind": "system", "status": "ok", "len": len(body)})
        print(f"  [system] OK {len(body):5d}b - {title[:50]}")
        time.sleep(0.2)
    return docs


# 게시판 목록의 게시글 링크: ?mode=view&articleNo=NNN
ARTICLE_RE = re.compile(r"(\?mode=view&(?:amp;)?articleNo=\d+)")


def discover_req_posts() -> list[str]:
    """졸업요건 게시판 목록 페이지에서 게시글 상세 URL 추출."""
    html = safe_get(REQ_BOARD_URL)
    if not html:
        return []
    rels = ARTICLE_RE.findall(html)
    urls: list[str] = []
    seen: set[str] = set()
    for rel in rels:
        rel = rel.replace("&amp;", "&")
        # articleNo 만 남기고 정규화(offset/limit 제거 → 중복 방지)
        m = re.search(r"articleNo=(\d+)", rel)
        if not m:
            continue
        no = m.group(1)
        if no in seen:
            continue
        seen.add(no)
        urls.append(f"{REQ_BOARD_URL}?mode=view&articleNo={no}")
    return urls


def crawl_req_posts(report: list[dict]) -> list[dict]:
    """졸업요건 게시판 각 게시글 상세 본문 수집(실제 졸업 규정 본문)."""
    posts = discover_req_posts()
    print(f"  [req-board] 게시글 후보: {len(posts)}건")
    docs: list[dict] = []
    for i, url in enumerate(posts, 1):
        html = safe_get(url)
        if not html:
            report.append({"url": url, "kind": "req_post", "status": "fetch_fail"})
            continue
        body = extract_main_text(html, min_len=MIN_LEN)
        if not body or len(body) < MIN_LEN:
            report.append({"url": url, "kind": "req_post", "status": "no_body",
                           "len": len(body) if body else 0})
            continue
        title = page_title(html, "졸업요건 게시글")
        docs.append(make_doc(url, title, body, "B_academic"))
        report.append({"url": url, "kind": "req_post", "status": "ok", "len": len(body)})
        print(f"  [req-board] [{i}/{len(posts)}] OK {len(body):5d}b - {title[:46]}")
        time.sleep(0.2)
    return docs


def _norm_body(s: str) -> str:
    """공백/개행 정규화한 본문 키(내용 중복 판정용)."""
    return re.sub(r"\s+", " ", s or "").strip()


def dedup(docs: list[dict]) -> list[dict]:
    """source_url + 본문 내용 기준 중복 제거(앞선 것 우선).

    이수체계도처럼 URL은 달라도 본문(연도 링크 목록)이 동일한 thin-noise를 걸러낸다.
    """
    seen_url: set[str] = set()
    seen_body: set[str] = set()
    out: list[dict] = []
    for d in docs:
        u = d["source_url"]
        if u in seen_url:
            continue
        bkey = _norm_body(d["content"])
        if bkey in seen_body:
            print(f"  [dedup] 본문 중복 제외: {u}")
            continue
        seen_url.add(u)
        seen_body.add(bkey)
        out.append(d)
    return out


def main() -> None:
    report: list[dict] = []
    print("[1/3] 정적 학부 페이지")
    static_docs = crawl_static(report)
    print("[2/3] 교과목 이수체계도(최근 연도)")
    system_docs = crawl_system(report)
    print("[3/3] 졸업요건 게시판 상세")
    req_docs = crawl_req_posts(report)

    all_docs = dedup(static_docs + system_docs + req_docs)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(all_docs, f, ensure_ascii=False, indent=2)

    ok = sum(1 for r in report if r["status"] == "ok")
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "totals": {
                "static": len(static_docs),
                "system": len(system_docs),
                "req_posts": len(req_docs),
                "all_after_dedup": len(all_docs),
                "report_ok": ok,
            },
            "items": report,
        }, f, ensure_ascii=False, indent=2)

    print("=" * 60)
    print(f"정적: {len(static_docs)} | 이수체계: {len(system_docs)} | 졸업요건글: {len(req_docs)}")
    print(f"총 문서(중복제거): {len(all_docs)}건")
    print("샘플 제목:")
    for d in all_docs[:8]:
        print(f"  - [{d['data_category']}] {d['title'][:60]} ({len(d['content'])}b)")
    print(f"저장: {OUT_PATH}")
    print(f"리포트: {REPORT_PATH}")


if __name__ == "__main__":
    main()
