from datetime import datetime, timedelta
from .base import BaseCrawler


class FacilitiesCrawler(BaseCrawler):
    """카테고리 H: 캠퍼스 시설(위치/예약) 크롤러."""

    category_id = "H_facilities"
    category_name = "캠퍼스 시설"
    freshness_tier = "static"
    BASE_URL = "https://www.cnu.ac.kr/facilities"

    def crawl(self) -> list[dict]:
        return self._fallback()

    def _fallback(self) -> list[dict]:
        now = datetime.utcnow().isoformat()
        valid = (datetime.utcnow() + timedelta(days=30)).isoformat()
        today = now[:10]
        items = [
            "충남대 정문: 대전광역시 유성구 대학로 99. 지하철 유성온천역에서 도보 15분 또는 버스.",
            "중앙도서관: 캠퍼스 중앙부. 지하1층~지상5층. 열람실, 디지털자료실, 스터디룸.",
            "학생회관: 학생 편의시설(식당, 카페, 동아리방) 집중. 중앙광장 북쪽.",
            "공과대학 건물군: 캠퍼스 동쪽. 33호관~50호관 구역.",
            "인문사회 건물군: 캠퍼스 서쪽. 1~15호관 구역.",
            "스포츠센터: 캠퍼스 북동쪽. 수영장, 헬스장, 체육관 운영. 학생 이용권 학기당 5만원.",
            "대강당: 본부 건물 옆. 대규모 행사·공연 개최.",
        ]
        return [self._make_doc("충남대 시설 (더미)", item, self.BASE_URL, now, valid, today) for item in items]
