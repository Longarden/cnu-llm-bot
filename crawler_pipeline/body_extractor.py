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
    """trafilatura 본문 추출. 의미 있는 길이 이상일 때만 반환.

    trafilatura 실패시 BS4로 알려진 본문 셀렉터(plus.cnu.ac.kr 게시판 등) 폴백.
    """
    # 1. trafilatura
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
    # 2. BS4 폴백 - 알려진 본문 컨테이너 클래스 (plus.cnu.ac.kr 게시판 view 등)
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        for cls in ("board_viewDetail", "board_view_cont", "bbs_content",
                    "view_cont", "view-cont", "editor_view", "bbs_view_cont",
                    "b-text-box", "b-box02", "article-body", "bbs_view_content",
                    "content-body", "view-body", "board-content"):
            el = soup.find(class_=cls)
            if not el:
                continue
            body = el.get_text(separator="\n", strip=True)
            if not body:
                continue
            body = repair_encoding(body)
            if len(body) < min_len:
                continue
            # 같은 페이지의 제목/메타 함께 묶어 풍부하게
            extras = []
            for tcls in ("board_viewTit", "board_viewHtit"):
                tel = soup.find(class_=tcls)
                if tel:
                    t = repair_encoding(tel.get_text(strip=True))
                    if t and t not in body:
                        extras.append(t)
            for mcls in ("board_viewInfo",):
                mel = soup.find(class_=mcls)
                if mel:
                    m = repair_encoding(mel.get_text(separator=" ", strip=True))
                    if m:
                        extras.append(m)
            full = "\n".join(extras + [body])
            return full
    except Exception:
        pass
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


def fetch_post(url: str, timeout: int = 20, min_len: int = 40,
               include_attachments: bool = False) -> dict | None:
    """게시판 상세 URL -> {'url','title','date','text'} 또는 None.

    trafilatura → BS4 폴백으로 본문 추출. 본문 부실시 None.
    include_attachments=True 면 첨부 HWP/PDF 텍스트도 본문 뒤에 합친다.
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
    # 첨부 본문 합본
    if include_attachments:
        try:
            from .attachment_parser import fetch_attachments_text
            atch_text = fetch_attachments_text(html, url)
            if atch_text:
                body = body + "\n\n" + atch_text
        except Exception:
            pass
    # 제목: 본문 첫 줄(표 구분자 정리), trafilatura 본문은 보통 글 제목으로 시작
    first = body.lstrip("| \n").split("\n", 1)[0].strip(" |")
    title = first[:80] if first else url
    # 날짜: YYYY-MM-DD / YYYY.MM.DD 패턴
    import re
    m = re.search(r"\d{4}[-.]\d{2}[-.]\d{2}", html)
    date_str = m.group(0).replace(".", "-") if m else ""
    return {"url": url, "title": title, "date": date_str, "text": body}
