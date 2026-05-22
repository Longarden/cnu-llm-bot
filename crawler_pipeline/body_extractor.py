"""상세페이지 본문 추출 (SOTA: trafilatura). 공지 등 '글 링크 -> 본문' 용도.

- fetch_html: 인코딩 자동 보정해서 HTML 가져옴(한국어 페이지 mojibake 원천 차단).
- extract_main_text: trafilatura로 본문만 추출(메뉴/광고/버튼 제거). 실패시 None.
- fetch_body: url -> 본문 텍스트. 실패시 None (호출측에서 제목 폴백).
"""
import requests
from .text_repair import repair_encoding

_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def fetch_html(url: str, timeout: int = 10) -> str:
    resp = requests.get(url, timeout=timeout, headers=_HEADERS)
    resp.raise_for_status()
    # requests가 charset 헤더 없을 때 latin1로 잘못 잡는 것을 보정(한국어 깨짐 방지)
    enc = (resp.encoding or "").lower()
    if not enc or enc in ("iso-8859-1", "latin-1", "ascii"):
        resp.encoding = resp.apparent_encoding or resp.encoding
    return resp.text


def extract_main_text(html: str, min_len: int = 40) -> str | None:
    """trafilatura 본문 추출. 의미 있는 길이 이상일 때만 반환."""
    try:
        import trafilatura
        txt = trafilatura.extract(
            html, include_comments=False, include_tables=True, favor_recall=True
        )
    except Exception:
        txt = None
    if txt:
        txt = repair_encoding(txt.strip())
        if len(txt) >= min_len:
            return txt
    return None


def fetch_body(url: str, timeout: int = 10, min_len: int = 40) -> str | None:
    """상세페이지 url -> 본문 텍스트. 네트워크/추출 실패시 None."""
    if not url or not url.startswith("http"):
        return None
    try:
        html = fetch_html(url, timeout=timeout)
    except Exception:
        return None
    return extract_main_text(html, min_len=min_len)


def fetch_post(url: str, timeout: int = 20, min_len: int = 40) -> dict | None:
    """게시판 상세 URL -> {'url','title','date','text'} 또는 None.

    trafilatura로 본문 추출. 본문이 부실하면 None을 반환해
    '게시물 NNNN' 같은 쓰레기 문서가 저장되는 것을 막는다(셀렉터 의존 제거).
    """
    if not url or not url.startswith("http"):
        return None
    try:
        html = fetch_html(url, timeout=timeout)
    except Exception:
        return None
    body = extract_main_text(html, min_len=min_len)
    if not body:
        return None
    # 제목: 본문 첫 줄(표 구분자 정리), trafilatura 본문은 보통 글 제목으로 시작
    first = body.lstrip("| \n").split("\n", 1)[0].strip(" |")
    title = first[:80] if first else url
    # 날짜: YYYY-MM-DD / YYYY.MM.DD 패턴
    import re
    m = re.search(r"\d{4}[-.]\d{2}[-.]\d{2}", html)
    date_str = m.group(0).replace(".", "-") if m else ""
    return {"url": url, "title": title, "date": date_str, "text": body}
