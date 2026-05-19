from datetime import datetime, timedelta
from .base import BaseCrawler


class ScholarshipCrawler(BaseCrawler):
    """카테고리 D: 장학/지원 크롤러."""

    category_id = "D_scholarship"
    category_name = "장학/지원"
    freshness_tier = "semi_static"
    BASE_URL = "https://jangjak.cnu.ac.kr"

    def crawl(self) -> list[dict]:
        return self._fallback()

    def _fallback(self) -> list[dict]:
        now = datetime.utcnow().isoformat()
        valid = (datetime.utcnow() + timedelta(days=7)).isoformat()
        today = now[:10]
        items = [
            "국가장학금(1유형): 소득분위 8구간 이하 신청 가능. 한국장학재단(www.kosaf.go.kr) 신청.",
            "국가장학금(2유형): 대학 자체 선발. 성적 기준 B+ 이상, 소득분위 8구간 이하.",
            "교내 성적우수장학금: 직전 학기 성적 상위 10% 이내. 자동 선발, 별도 신청 불필요.",
            "근로장학금: 교내 부서 배치. 시간당 9,000원 이상. 매 학기 초 포털 신청.",
            "긴급복지장학금: 갑작스러운 가정 형편 악화 시 신청. 학생지원처 상담 후 서류 제출.",
            "충남대 장학금 신청: 포털(plus.cnu.ac.kr) → 등록/장학 → 장학금 신청.",
        ]
        return [self._make_doc("충남대 장학 정보 (더미)", item, self.BASE_URL, now, valid, today) for item in items]
