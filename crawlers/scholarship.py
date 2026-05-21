"""충남대 장학/지원 크롤러 - 실제 크롤 구현."""
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
BOARD_CODE = "sub07_0713"
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
        title = title_tag.get_text(strip=True) if title_tag else f"장학 게시물 {ntt_no}"

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


def _fetch_board_nos(code: str = BOARD_CODE, pages: int = 4) -> list[str]:
    nos = []
    for page in range(1, pages + 1):
        url = f"{BASE_URL}/_prog/_board/?code={code}&site_dvs_cd=kr&menu_dvs_cd=0713&page={page}"
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
            logger.warning("장학 게시판 페이지 %d 실패: %s", page, e)
    return nos


class ScholarshipCrawler(BaseCrawler):
    """카테고리 D: 장학/지원 크롤러."""

    category_id = "D_scholarship"
    category_name = "장학/지원"
    freshness_tier = "semi_static"
    BASE_URL = BASE_URL

    def crawl(self) -> list[dict]:
        now = datetime.utcnow().isoformat()
        valid = (datetime.utcnow() + timedelta(days=7)).isoformat()
        docs = []

        # 장학 게시판 게시물
        known_nos = [
            "2513193", "2513192", "2513188", "2513090", "2513024",
            "2513013", "2513012", "2513011", "2513010", "2512991",
        ]
        board_nos = _fetch_board_nos(BOARD_CODE, pages=4)
        all_nos = list(dict.fromkeys(known_nos + board_nos))

        for ntt_no in all_nos[:30]:
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

        # 정적 핵심 장학 정보
        static_items = [
            ("국가장학금 1유형", "소득분위 8구간 이하 신청 가능. 한국장학재단(www.kosaf.go.kr) 신청. 매 학기 초 신청 기간 확인 필수."),
            ("국가장학금 2유형", "대학 자체 선발. 성적 기준 B+ 이상, 소득분위 8구간 이하. 포털에서 신청."),
            ("교내 성적우수장학금", "직전 학기 성적 상위 10% 이내 자동 선발. 별도 신청 불필요. 등록금 일부 또는 전액 지원."),
            ("근로장학금", "교내 부서 배치. 시간당 법정 최저임금 이상. 매 학기 초 포털 신청. 주당 최대 20시간."),
            ("긴급복지장학금", "갑작스러운 가정 형편 악화 시 신청. 학생지원처 상담 후 서류 제출. 학기 중 수시 신청 가능."),
            ("장학금 신청 방법", "포털(plus.cnu.ac.kr) → 등록/장학 → 장학금 신청. 신청 기간 내 서류 제출 필수."),
            ("산학협동재단 장학금", "디딤돌 장학금(4년제 신입생, 월 80만원), 외국인 근로자 자녀 장학금 등. 학생과 공지 확인."),
            ("세종이도인재장학금", "세종특별자치시 1년 이상 거주자 대상. 신청 기간 및 금액 공고 참조."),
            ("화성시인재육성재단 장학금", "화성시 거주 비수도권 대학 재학생 대상. 연간 최대 200만원 주거비 지원."),
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

        logger.info("scholarship 크롤 완료: %d 건", len(docs))
        return docs


def crawl() -> list[dict]:
    return ScholarshipCrawler().crawl()
