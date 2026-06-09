"""충남대 학사(수강/졸업/일정) 크롤러 - 실제 크롤 구현."""
from datetime import datetime, timedelta
from .base import BaseCrawler
import os
import requests
from bs4 import BeautifulSoup
import io
import logging

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9",
}
BASE_URL = "https://plus.cnu.ac.kr"
BOARD_CODE = "sub07_0702"
TIMEOUT = 30


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    """PDF 바이트에서 텍스트 추출."""
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
    """첨부파일 다운로드."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if r.status_code == 200:
            return r.content
    except Exception as e:
        logger.warning("첨부파일 다운로드 실패 %s: %s", url, e)
    return None


def _fetch_post(ntt_no: str, code: str = BOARD_CODE, timeout: int = TIMEOUT) -> dict | None:
    """상세 게시물 -> 본문(trafilatura). 본문 없으면 None('게시물 NNNN' 쓰레기 방지)."""
    url = f"{BASE_URL}/_prog/_board/?code={code}&mode=V&no={ntt_no}"
    from crawler_pipeline.body_extractor import fetch_post
    return fetch_post(url, timeout=timeout)


def _fetch_board_nos(code: str = BOARD_CODE, menu_dvs_cd: str = "07020101", pages: int = 3,
                     timeout: int = TIMEOUT) -> list[str]:
    """게시판 목록에서 게시물 번호 수집."""
    nos = []
    for page in range(1, pages + 1):
        url = (
            f"{BASE_URL}/_prog/_board/?code={code}"
            f"&site_dvs_cd=kr&menu_dvs_cd={menu_dvs_cd}&page={page}"
        )
        try:
            r = requests.get(url, headers=HEADERS, timeout=timeout)
            r.raise_for_status()
            r.encoding = "utf-8"
            soup = BeautifulSoup(r.text, "html.parser")
            import re
            for a in soup.select("a[href*='no=']"):
                href = a.get("href", "")
                m = re.search(r"no=(\d+)", href)
                if m and m.group(1) not in nos:
                    nos.append(m.group(1))
        except Exception as e:
            logger.warning("게시판 %s 페이지 %d 실패: %s", code, page, e)
    return nos


class AcademicCrawler(BaseCrawler):
    """카테고리 B: 학사(수강/졸업/일정) 크롤러."""

    category_id = "B_academic"
    category_name = "학사"
    freshness_tier = "semi_static"
    BASE_URL = BASE_URL

    def crawl(self) -> list[dict]:
        now = datetime.utcnow().isoformat()
        valid = (datetime.utcnow() + timedelta(days=7)).isoformat()
        docs = []

        # 1) 학사일정 페이지
        try:
            cal_url = f"{BASE_URL}/_prog/academic_calendar/?site_dvs_cd=kr&menu_dvs_cd=05020101"
            r = requests.get(cal_url, headers=HEADERS, timeout=TIMEOUT)
            r.encoding = "utf-8"
            soup = BeautifulSoup(r.text, "html.parser")
            cal_text = soup.get_text(separator="\n", strip=True)
            if cal_text:
                docs.append(self._make_doc(
                    title="2026학년도 학사일정",
                    content=cal_text[:3000],
                    source_url=cal_url,
                    now=now,
                    valid=valid,
                    date=now[:10],
                ))
        except Exception as e:
            logger.warning("학사일정 크롤 실패: %s", e)

        # 2) 학사 공지 게시판 게시물 수집 (알려진 no 목록 + 동적 수집)
        known_nos = [
            "2513150", "2513134", "2513124", "2512782", "2512124", "2511200",
            "2513194", "2513161",
        ]
        # 동적 수집
        board_nos = _fetch_board_nos(BOARD_CODE, "07020101", pages=10)
        all_nos = list(dict.fromkeys(known_nos + board_nos))  # 중복 제거, 순서 유지

        for ntt_no in all_nos[:100]:
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

        # 3) 정적 핵심 학사 정보 (수강신청/졸업/성적 등 – 포털 직접 접근 불가 시 보완용)
        static_items = [
            ("수강신청 안내", "수강신청은 매 학기 개강 약 2주 전 포털(plus.cnu.ac.kr)에서 학년별 순차 진행. 변경기간은 개강 후 2주차. 포털 → 학사정보 → 수강신청."),
            ("졸업 요건", "4년제 기준 졸업학점 130학점 이상, 교양 35학점, 전공 60학점, 졸업평점 2.0 이상 필요. 졸업시험 또는 논문 요건 학과별 상이."),
            ("성적 조회·이의신청", "성적은 포털 → 학사정보 → 성적조회 메뉴. 이의신청 기간은 성적 공개 후 1주일 이내."),
            ("휴학·복학 신청", "휴학은 개강 후 4주 이내 포털 신청. 군 휴학은 입영통지서 첨부. 복학은 복학 예정 학기 전 학기 수강신청 기간 내 신청."),
            ("수강철회", "매 학기 8~9주차 1주일간 포털에서 수강철회 신청 가능. 성적 미산입, W 표기."),
            ("계절학기", "하기·동기 계절학기 운영. 수강신청은 포털에서 별도 기간에 진행. 수업료 별도 납부."),
            ("학사일정 요약 2026", "3.3 제1학기 개강, 6.22 하기방학, 9.1 제2학기 개강, 12.21 동기계절학기. 졸업식: 2.25(전기), 8.25(후기)."),
            ("타대학 학점교류", "국내 54개 협약 대학 수강 가능. 직전 학기 평점 1.75 이상, 1학기 이상 이수한 재학생. 포털 → 통합정보시스템 → 교외활동신청 → 타대학학점교류신청."),
            ("출석인정 신청", "질병·공적 사유 발생 시 포털에서 출석인정 신청. 증빙서류 첨부 필수. 매뉴얼은 학사지원과 공지 참조."),
            ("현장실습(백마인턴십)", "하계 계절학기 중 기업 현장실습. 학점 인정 가능. 신청은 포털 → 학사정보 → 현장실습 메뉴."),
            ("학사 문의처", "학사지원과: 042-821-5050, 대학본부 1호관 202호. 포털 온라인 FAQ 및 학사상담 게시판 이용 가능."),
            ("전공 변경·이중전공", "전공 변경은 학기 초 신청 기간 내 포털 신청. 이중전공·부전공은 별도 신청 기간 운영. 정원 제한 있음."),
            ("강의평가", "매 학기 말 강의평가 실시. 포털 → 학사정보 → 강의평가. 평가 미완료 시 성적 조회 제한 가능."),
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

        docs.append(self._holiday_2026_doc())  # 2026 공휴일/임시공휴일 정적표(코퍼스에도 포함)
        logger.info("academic 크롤 완료: %d 건", len(docs))
        return docs

    def _holiday_2026_doc(self) -> dict:
        """2026 대한민국 공휴일(휴강·휴무 기준) 정적 문서.

        '임시공휴일(지방선거일 등)'은 학사 캘린더 반영이 늦거나 누락될 수 있어, 결정론적으로
        잡도록 코퍼스/라이브 양쪽에 주입한다. 출처 검증(publicholidays) 후 빨간날 아닌 제헌절은
        제외하고, 6/3 제9회 전국동시지방선거일(법정공휴일)을 포함. freshness_tier=static.
        """
        now = datetime.utcnow().isoformat()
        valid = "2026-12-31T00:00:00"
        content = (
            "2026년 대한민국 공휴일(대학 휴강·휴무 기준):\n"
            "- 1월 1일(목) 신정\n"
            "- 2월 16일(월)~18일(수) 설날 연휴\n"
            "- 3월 1일(일) 삼일절 / 3월 2일(월) 대체공휴일\n"
            "- 5월 5일(화) 어린이날\n"
            "- 5월 24일(일) 부처님오신날 / 5월 25일(월) 대체공휴일\n"
            "- 6월 3일(수) 제9회 전국동시지방선거일 (법정공휴일)\n"
            "- 6월 6일(토) 현충일\n"
            "- 8월 15일(토) 광복절 / 8월 17일(월) 대체공휴일\n"
            "- 9월 24일(목)~26일(토) 추석 연휴\n"
            "- 10월 3일(토) 개천절 / 10월 5일(월) 대체공휴일\n"
            "- 10월 9일(금) 한글날\n"
            "- 12월 25일(금) 성탄절\n"
            "공휴일은 정상 휴강·휴무이며, 임시공휴일은 정부 지정에 따른다."
        )
        return {
            "source_url": "https://www.cnu.ac.kr",
            "data_category": "B_academic",
            "last_crawled_at": now,
            "valid_until": valid,
            "freshness_tier": "static",
            "original_text": content,
            "title": "2026년 공휴일 및 임시공휴일 안내",
            "content": content,
            "date": now[:10],
        }

    def crawl_realtime(self, max_posts: int = 3) -> list[dict]:
        """라이브용 경량 크롤(채점 시점 단발 질문 응답용).

        풀 crawl()은 게시판 100건이라 단발 질의엔 무겁다. 여기서는
        (1) 학사일정 페이지(라이브) + (2) 학사 게시판 1페이지 최신글 일부만 긁어
        '이번에 바뀐 학사일정/졸업·수강 변경'에 빠르게 답한다. 실패 시 빈 리스트.

        [524 방지] 풀 crawl()용 TIMEOUT(30초)이 아니라 라이브 전용 CRAWL_TIMEOUT(기본 10초)을
        쓰고 max_posts=3 으로 제한 → 최악 (1+1+3)×10≈50초. 상위(chat_answer)의 공지 fan-out과
        합쳐도 100초 터널 한도 안에 들어온다.
        """
        rt = int(os.environ.get("CRAWL_TIMEOUT", "10"))
        now = datetime.utcnow().isoformat()
        valid = (datetime.utcnow() + timedelta(days=1)).isoformat()
        docs = []

        # (1) 학사일정 페이지(라이브)
        try:
            cal_url = f"{BASE_URL}/_prog/academic_calendar/?site_dvs_cd=kr&menu_dvs_cd=05020101"
            r = requests.get(cal_url, headers=HEADERS, timeout=rt)
            r.encoding = "utf-8"
            soup = BeautifulSoup(r.text, "html.parser")
            cal_text = soup.get_text(separator="\n", strip=True)
            if cal_text:
                docs.append(self._make_doc(
                    title="학사일정(실시간)", content=cal_text[:3000],
                    source_url=cal_url, now=now, valid=valid, date=now[:10],
                ))
        except Exception as e:
            logger.warning("학사일정 실시간 크롤 실패: %s", e)

        # (2) 학사 게시판 최신글 일부(졸업/수강 변경 공지 등) — 1페이지, 상위 max_posts건만
        try:
            nos = _fetch_board_nos(BOARD_CODE, "07020101", pages=1, timeout=rt)
            for ntt_no in nos[:max_posts]:
                post = _fetch_post(ntt_no, BOARD_CODE, timeout=rt)
                if post and post["text"].strip():
                    docs.append(self._make_doc(
                        title=post["title"], content=post["text"],
                        source_url=post["url"], now=now, valid=valid,
                        date=post["date"] or now[:10],
                    ))
        except Exception as e:
            logger.warning("학사 게시판 실시간 크롤 실패: %s", e)

        # (3) 2026 공휴일/임시공휴일 정적표 — 캘린더 누락/지연 대비 결정론적 주입.
        docs.append(self._holiday_2026_doc())
        return docs


def crawl() -> list[dict]:
    return AcademicCrawler().crawl()
