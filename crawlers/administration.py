"""충남대 행정/증명서 크롤러 - 실제 크롤 구현."""
from datetime import datetime, timedelta
from .base import BaseCrawler
import requests
from bs4 import BeautifulSoup
import io
import re
import logging

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9",
}
BASE_URL = "https://plus.cnu.ac.kr"
BOARD_CODE = "sub07_0701"
TIMEOUT = 30


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    text = ""
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text += t + "\n"
        return text.strip()
    except Exception:
        pass
    try:
        import PyPDF2
        reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
        for page in reader.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"
        return text.strip()
    except Exception as e:
        logger.warning("PDF 추출 실패: %s", e)
        return ""


def _download_attachment(url: str) -> bytes | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if r.status_code == 200:
            return r.content
    except Exception as e:
        logger.warning("첨부파일 다운로드 실패 %s: %s", url, e)
    return None


def _fetch_post(ntt_no: str, code: str = BOARD_CODE) -> dict | None:
    url = f"{BASE_URL}/_prog/_board/?code={code}&mode=V&no={ntt_no}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        r.encoding = "utf-8"
        soup = BeautifulSoup(r.text, "html.parser")

        title_tag = soup.select_one(".board_view_title, .view_title, h3.title, .bbs_title")
        title = title_tag.get_text(strip=True) if title_tag else f"게시물 {ntt_no}"

        date_tag = soup.select_one(".date, .board_date, .reg_date, td.date")
        date_str = date_tag.get_text(strip=True) if date_tag else ""
        if not date_str:
            m = re.search(r"\d{4}-\d{2}-\d{2}", r.text)
            date_str = m.group(0) if m else ""

        body_tag = soup.select_one(".board_view_content, .view_content, .bbs_content, .content_view")
        body = body_tag.get_text(separator="\n", strip=True) if body_tag else ""

        attach_texts = []
        for a in soup.select("a[href*='download.php'], a[href*='atch_no']"):
            href = a.get("href", "")
            if not href.startswith("http"):
                href = BASE_URL + ("/" if not href.startswith("/") else "") + href
            fname = a.get_text(strip=True).lower()
            if fname.endswith(".pdf"):
                data = _download_attachment(href)
                if data:
                    t = _extract_pdf_text(data)
                    if t:
                        attach_texts.append(t)

        full_text = body
        if attach_texts:
            full_text += "\n\n[첨부파일 내용]\n" + "\n".join(attach_texts)
        if not full_text.strip():
            full_text = title

        return {"url": url, "title": title, "date": date_str, "text": full_text}
    except Exception as e:
        logger.warning("게시물 %s 크롤 실패: %s", ntt_no, e)
        return None


def _fetch_board_nos(code: str = BOARD_CODE, menu_dvs_cd: str = "07010101", pages: int = 3) -> list[str]:
    nos = []
    for page in range(1, pages + 1):
        url = (
            f"{BASE_URL}/_prog/_board/?code={code}"
            f"&site_dvs_cd=kr&menu_dvs_cd={menu_dvs_cd}&page={page}"
        )
        try:
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            r.raise_for_status()
            r.encoding = "utf-8"
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.select("a[href*='no=']"):
                href = a.get("href", "")
                m = re.search(r"no=(\d+)", href)
                if m and m.group(1) not in nos:
                    nos.append(m.group(1))
        except Exception as e:
            logger.warning("게시판 %s 페이지 %d 실패: %s", code, page, e)
    return nos


class AdministrationCrawler(BaseCrawler):
    """카테고리 C: 행정/증명서 크롤러."""

    category_id = "C_administration"
    category_name = "행정/증명서"
    freshness_tier = "semi_static"
    BASE_URL = BASE_URL

    def crawl(self) -> list[dict]:
        now = datetime.utcnow().isoformat()
        valid = (datetime.utcnow() + timedelta(days=7)).isoformat()
        docs = []

        # 행정 공지 게시판 (새소식)
        known_nos = ["2511413", "2513186", "2513099", "2513094", "2513091",
                     "2513073", "2513068", "2513002", "2512989", "2512987"]
        board_nos = _fetch_board_nos(BOARD_CODE, "07010101", pages=3)
        all_nos = list(dict.fromkeys(known_nos + board_nos))

        for ntt_no in all_nos[:25]:
            post = _fetch_post(ntt_no, BOARD_CODE)
            if post and post["text"].strip():
                docs.append(self._make_doc(
                    title=post["title"],
                    content=post["text"],
                    source_url=post["url"],
                    now=now,
                    valid=valid,
                    date=post["date"] or now[:10],
                ))

        # 정적 핵심 행정 정보
        static_items = [
            ("재학증명서 발급", "재학증명서는 포털(plus.cnu.ac.kr) 로그인 후 온라인 발급 또는 교내 무인발급기(24시간) 이용. 수수료 없음."),
            ("성적증명서 발급", "성적증명서 포털 온라인 발급 가능 (영문 포함). 발급 수수료 500원/장. 우편 수령 신청 가능."),
            ("졸업증명서 발급", "졸업증명서 졸업 후 포털 또는 우편 신청. 처리 기간 3~5일. 영문 발급 가능."),
            ("등록금 납부", "등록금 고지서 포털 → 등록/장학 메뉴에서 출력. 납부 기간 내 은행 이체 또는 포털 납부."),
            ("학생증 발급", "학생증 입학 후 학생처 방문 발급. 재발급은 IC카드 신청서 제출. 분실 신고 필수."),
            ("휴학·복학 서류", "휴학·복학은 학사지원과(1호관 202호) 또는 포털 온라인 처리. 군 휴학 시 입영통지서 첨부."),
            ("전입신고 안내", "재학 중 주소 변경 시 거주지 관할 주민센터에 전입신고. 예비군 편입 관련 예비군연대 문의."),
            ("민원 처리 절차", "각종 민원은 포털 → 학사정보 → 민원신청 또는 해당 부서 직접 방문. 처리 기간 3~7일."),
            ("등록금 분할납부", "등록금 분할납부 신청은 포털 → 등록/장학 → 분할납부 신청. 2회 분납 가능, 이자 없음."),
            ("학적부 정정", "성명·주민번호 등 학적사항 정정은 학사지원과 방문 신청. 공적 서류(주민등록등본 등) 지참."),
            ("장기결석 처리", "질병 등 부득이한 사유로 장기결석 시 학사지원과에 사유서 및 증빙서류 제출."),
            ("군입대 관련 행정", "군 입대 전 군 휴학 신청 필수. 제대 후 복학 신청은 복학 예정 학기 수강신청 기간 내 포털 처리."),
            ("우수도서 출판지원", "충남대 출판문화원 주관 우수도서 출판지원 사업. 일반도서 200만원, 문고도서 100만원 지원. 연 1~2회 공모."),
        ]
        for title, content in static_items:
            docs.append(self._make_doc(
                title=title,
                content=content,
                source_url=BASE_URL,
                now=now,
                valid=valid,
                date=now[:10],
            ))

        logger.info("administration 크롤 완료: %d 건", len(docs))
        return docs


def crawl() -> list[dict]:
    return AdministrationCrawler().crawl()
