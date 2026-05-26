"""충남대 취업/진로 크롤러 - 실제 크롤 구현."""
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
# 채용/초빙 게시판
BOARD_CODE_RECRUIT = "sub07_0705"
# 새소식 게시판 (취업 관련 공지 포함)
BOARD_CODE_NEWS = "sub07_0701"
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


def _fetch_post(ntt_no: str, code: str) -> dict | None:
    """상세 게시물 -> 본문(trafilatura). 본문 없으면 None('게시물 NNNN' 쓰레기 방지)."""
    url = f"{BASE_URL}/_prog/_board/?code={code}&mode=V&no={ntt_no}"
    from crawler_pipeline.body_extractor import fetch_post
    return fetch_post(url, timeout=TIMEOUT)


def _fetch_board_nos(code: str, menu_dvs_cd: str, pages: int = 3) -> list[str]:
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


class CareerCrawler(BaseCrawler):
    """카테고리 E: 취업/진로 크롤러."""

    category_id = "E_career"
    category_name = "취업/진로"
    freshness_tier = "semi_static"
    BASE_URL = BASE_URL

    def crawl(self) -> list[dict]:
        now = datetime.utcnow().isoformat()
        valid = (datetime.utcnow() + timedelta(days=7)).isoformat()
        docs = []

        # 채용/초빙 게시판
        recruit_known = [
            "2513186", "2513099", "2513094", "2513073", "2513068",
            "2513002", "2512989", "2512987",
        ]
        recruit_nos = _fetch_board_nos(BOARD_CODE_RECRUIT, "07050101", pages=10)
        all_recruit = list(dict.fromkeys(recruit_known + recruit_nos))

        for ntt_no in all_recruit[:80]:
            post = _fetch_post(ntt_no, BOARD_CODE_RECRUIT)
            if post and post["text"].strip():
                docs.append(self._make_doc(
                    title=post["title"],
                    content=post["text"],
                    source_url=post["url"],
                    now=now,
                    valid=valid,
                    date=post["date"] or now[:10],
                ))

        # 새소식 게시판 취업 관련 게시물
        news_known = ["2513161", "2513194"]
        news_nos = _fetch_board_nos(BOARD_CODE_NEWS, "07010101", pages=10)
        # 취업/채용 키워드 필터링 (제목 텍스트는 없으므로 일단 수집)
        all_news = list(dict.fromkeys(news_known + news_nos))

        career_keywords = ["채용", "취업", "인턴", "박람회", "설명회", "진로", "현장실습", "취창업"]
        for ntt_no in all_news[:80]:
            post = _fetch_post(ntt_no, BOARD_CODE_NEWS)
            if post and post["text"].strip():
                # 취업 관련 키워드가 제목 또는 본문에 있는 경우만
                combined = post["title"] + post["text"]
                if any(kw in combined for kw in career_keywords):
                    docs.append(self._make_doc(
                        title=post["title"],
                        content=post["text"],
                        source_url=post["url"],
                        now=now,
                        valid=valid,
                        date=post["date"] or now[:10],
                    ))

        # 정적 핵심 취업/진로 정보
        static_items = [
            ("취업지원센터 안내", "취업지원센터 위치: 충남대 대학본부 1층. 전화 042-821-7051. 이력서 첨삭, 모의면접, 진로상담 서비스 운영."),
            ("채용공고 확인 방법", "충남대 포털(plus.cnu.ac.kr) → 새소식 → 채용/초빙 게시판에서 최신 채용 공고 확인 가능."),
            ("취업특강 프로그램", "매 학기 이력서 작성, 면접 기법, 직무분석 특강 운영. 취업지원센터 홈페이지에서 일정 확인."),
            ("현장실습(인턴십)", "학점 인정 현장실습(백마인턴십) 운영. 하계·동계 방학 중 협약 기업 파견. 학사지원과 신청."),
            ("진로상담 예약", "취업지원센터 개인 진로 상담 예약 가능. 전화(042-821-7051) 또는 방문 예약."),
            ("글로벌 채용박람회", "2026 GLOBAL TALENT FAIR 채용박람회 참여 안내. 외국계 기업 취업 준비생 대상."),
            ("청년인턴 채용", "충남대 청년인턴 채용시험. 2026년 최종합격자 공고 확인(포털 채용/초빙 게시판)."),
            ("취업 통계", "직전 연도 졸업생 취업률은 취업지원센터 홈페이지 공시 데이터 참조. 학과별 취업률 상이."),
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

        logger.info("career 크롤 완료: %d 건", len(docs))
        return docs


def crawl() -> list[dict]:
    return CareerCrawler().crawl()
