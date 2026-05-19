from datetime import datetime, timedelta
from .base import BaseCrawler


class DormitoryCrawler(BaseCrawler):
    """카테고리 G1: 기숙사 크롤러."""

    category_id = "G_dormitory"
    category_name = "기숙사"
    freshness_tier = "semi_static"
    BASE_URL = "https://dorm.cnu.ac.kr"

    def crawl(self) -> list[dict]:
        return self._fallback()

    def _fallback(self) -> list[dict]:
        now = datetime.utcnow().isoformat()
        valid = (datetime.utcnow() + timedelta(days=14)).isoformat()
        today = now[:10]
        items = [
            "충남대 생활관: 남학생관, 여학생관, 국제학생관 운영. 수용 인원 약 3,000명.",
            "생활관 신청: 매 학기 포털(plus.cnu.ac.kr) → 학생지원 → 생활관 신청.",
            "생활관 비용: 1인실 약 40만원/학기, 2인실 약 28만원/학기 (식사 포함 옵션 별도).",
            "생활관 규정: 외박 신청 필수, 방문객 외부 공간까지만 허용, 취침 후 정숙 필수.",
            "생활관 시설: 세탁실(무료), 헬스장, 편의점, 독서실 운영.",
        ]
        return [self._make_doc("충남대 기숙사 (더미)", item, self.BASE_URL, now, valid, today) for item in items]
