from datetime import datetime, timedelta
from .base import BaseCrawler
import requests
from bs4 import BeautifulSoup


class AcademicCrawler(BaseCrawler):
    """카테고리 B: 학사(수강/졸업/일정) 크롤러."""

    category_id = "B_academic"
    category_name = "학사"
    freshness_tier = "semi_static"
    BASE_URL = "https://plus.cnu.ac.kr"

    def crawl(self) -> list[dict]:
        return self._fallback()

    def _fallback(self) -> list[dict]:
        now = datetime.utcnow().isoformat()
        valid = (datetime.utcnow() + timedelta(days=7)).isoformat()
        today = now[:10]
        items = [
            "수강신청 기간: 매 학기 개강 2주 전 (학년별 순차 신청). 포털(plus.cnu.ac.kr) 에서 신청.",
            "졸업 요건: 4년제 기준 130학점 이상, 교양 35학점, 전공 60학점, GPA 2.0 이상.",
            "성적 조회: 포털 로그인 → 학사정보 → 성적 조회. 중간/기말 성적은 학기 종료 후 2주 내 공개.",
            "휴학 신청: 학기 개강 후 4주 이내 포털 신청. 군 휴학은 입영통지서 첨부 필요.",
            "복학 신청: 복학 예정 학기 전 학기 수강신청 기간 내 포털 신청.",
            "학사 일정: 충남대 학사지원과(042-821-5050) 또는 홈페이지 공지 확인.",
            "수강철회: 매 학기 8~9주차 1주일간 포털에서 신청 가능 (성적 미산입, W 표기).",
        ]
        return [self._make_doc("충남대 학사 정보 (더미)", item, self.BASE_URL, now, valid, today) for item in items]
