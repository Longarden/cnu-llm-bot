from datetime import datetime, timedelta
from .base import BaseCrawler


class ExtracurricularCrawler(BaseCrawler):
    """카테고리 J: 비교과/대외활동 크롤러."""

    category_id = "J_extracurricular"
    category_name = "비교과/대외활동"
    freshness_tier = "semi_static"
    BASE_URL = "https://www.cnu.ac.kr/extracurricular"

    def crawl(self) -> list[dict]:
        return self._fallback()

    def _fallback(self) -> list[dict]:
        now = datetime.utcnow().isoformat()
        valid = (datetime.utcnow() + timedelta(days=14)).isoformat()
        today = now[:10]
        items = [
            "비교과 프로그램: 충남대 교육혁신본부 운영. 리더십, 봉사, 창업, 취업 관련 다수.",
            "대외활동 지원: 공모전, 서포터즈, 봉사활동 등. 대외활동 포털(스펙업 등) 연계.",
            "창업지원단: 학생 창업 아이디어 지원. 창업 공간(창업보육센터) 제공.",
            "자원봉사: 사회봉사 교과목 1학점 인정. 학기당 15시간 이상 필요.",
            "학생 공모전: 매 학기 학교 주관 UCC, 아이디어, 글짓기 공모전 운영.",
        ]
        return [self._make_doc("충남대 비교과/대외활동 (더미)", item, self.BASE_URL, now, valid, today) for item in items]
