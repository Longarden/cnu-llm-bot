from datetime import datetime, timedelta
from .base import BaseCrawler


class InternationalCrawler(BaseCrawler):
    """카테고리 I: 국제/교환 크롤러."""

    category_id = "I_international"
    category_name = "국제/교환"
    freshness_tier = "semi_static"
    BASE_URL = "https://silkroad.cnu.ac.kr"

    def crawl(self) -> list[dict]:
        return self._fallback()

    def _fallback(self) -> list[dict]:
        now = datetime.utcnow().isoformat()
        valid = (datetime.utcnow() + timedelta(days=14)).isoformat()
        today = now[:10]
        items = [
            "교환학생 파견: 협정 대학 60개국 이상. 매 학기 국제교류처(silkroad.cnu.ac.kr) 모집 공고.",
            "교환학생 지원 자격: GPA 2.5 이상, 외국어 능력 증빙(TOEFL, IELTS, HSK 등).",
            "외국인 유학생 지원: 한국어 교육, 버디 프로그램, 기숙사 우선 배정.",
            "국제교류처 위치: 대학본부 1층. 전화 042-821-5065.",
            "어학연수 프로그램: 방학 중 어학연수 장학금 지원. 매 학기 공고 확인.",
        ]
        return [self._make_doc("충남대 국제/교환 (더미)", item, self.BASE_URL, now, valid, today) for item in items]
