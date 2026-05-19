from datetime import datetime, timedelta
from .base import BaseCrawler


class CareerCrawler(BaseCrawler):
    """카테고리 E: 취업/진로 크롤러."""

    category_id = "E_career"
    category_name = "취업/진로"
    freshness_tier = "semi_static"
    BASE_URL = "https://ce.cnu.ac.kr"

    def crawl(self) -> list[dict]:
        return self._fallback()

    def _fallback(self) -> list[dict]:
        now = datetime.utcnow().isoformat()
        valid = (datetime.utcnow() + timedelta(days=3)).isoformat()
        today = now[:10]
        items = [
            "취업지원센터 위치: 충남대 대학본부 1층. 전화 042-821-7051.",
            "채용공고 확인: 충남대 취업지원시스템(ce.cnu.ac.kr) 또는 대학 포털 공지사항.",
            "취업특강: 매 학기 이력서·면접 특강 운영. 취업지원센터 홈페이지 일정 확인.",
            "현장실습(인턴십): 학점 인정 현장실습. 협약 기업 목록 취업지원센터 문의.",
            "진로상담: 취업지원센터 개인 진로 상담 예약 (전화 또는 방문).",
            "취업 통계: 직전년도 졸업생 취업률은 취업지원센터 홈페이지 공시 참고.",
        ]
        return [self._make_doc("충남대 취업/진로 (더미)", item, self.BASE_URL, now, valid, today) for item in items]
