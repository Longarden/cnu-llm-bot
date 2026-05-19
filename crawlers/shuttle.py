from datetime import datetime, timedelta
from .base import BaseCrawler


class ShuttleCrawler(BaseCrawler):
    """카테고리 A3: 셔틀버스 시간표 크롤러."""

    category_id = "A_shuttle"
    category_name = "셔틀버스"
    freshness_tier = "time_sensitive"
    BASE_URL = "https://www.cnu.ac.kr/life/shuttle.do"

    def crawl(self) -> list[dict]:
        return self._fallback()

    def _fallback(self) -> list[dict]:
        now = datetime.utcnow().isoformat()
        valid = (datetime.utcnow() + timedelta(days=1)).isoformat()
        today = now[:10]
        schedules = [
            "충남대 순환버스 노선1: 정문↔공과대↔생활관↔중앙도서관 (평일 08:00~18:00, 30분 간격)",
            "충남대 순환버스 노선2: 정문↔인문대↔사회과학대↔공과대 (평일 09:00~17:00, 1시간 간격)",
            "대덕캠퍼스 셔틀: 본교↔대덕캠퍼스 (평일 08:30, 13:00, 17:30 출발)",
            "지하철 연계 셔틀: 유성온천역↔정문 (평일 08:00~20:00, 20분 간격)",
            "야간 셔틀: 정문↔생활관 (평일 22:00, 23:00 운행)",
        ]
        return [self._make_doc("충남대 셔틀버스 (더미)", s, self.BASE_URL, now, valid, today) for s in schedules]
