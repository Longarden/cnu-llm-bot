from datetime import datetime, timedelta
from .base import BaseCrawler
import requests
from bs4 import BeautifulSoup


class LibraryCrawler(BaseCrawler):
    """카테고리 A2: 도서관 운영시간/서비스 크롤러."""

    category_id = "A_library"
    category_name = "도서관"
    freshness_tier = "time_sensitive"
    BASE_URL = "https://library.cnu.ac.kr"

    def crawl(self) -> list[dict]:
        now = datetime.utcnow().isoformat()
        valid = (datetime.utcnow() + timedelta(days=1)).isoformat()
        today = now[:10]
        try:
            resp = requests.get(self.BASE_URL, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            items = []
            for tag in soup.select("p, li, td"):
                t = tag.get_text(strip=True)
                if len(t) > 20:
                    items.append(self._make_doc("충남대 도서관 정보", t, self.BASE_URL, now, valid, today))
            return items[:10] if items else self._fallback()
        except Exception as e:
            print(f"[library] 크롤 실패: {e}")
            return self._fallback()

    def _fallback(self) -> list[dict]:
        now = datetime.utcnow().isoformat()
        valid = (datetime.utcnow() + timedelta(days=1)).isoformat()
        today = now[:10]
        infos = [
            "충남대 중앙도서관 운영시간: 평일 08:00~22:00, 토요일 09:00~17:00, 일요일 휴관",
            "열람실 좌석 예약: 도서관 홈페이지(library.cnu.ac.kr) 또는 앱에서 가능",
            "자료 대출: 학부생 10권(14일), 대학원생 20권(30일)",
            "상호대차 서비스: 타 대학 도서 신청 가능, 보통 3~5일 소요",
            "스터디룸 예약: 4인실, 8인실 운영. 하루 전 온라인 예약 필수",
        ]
        return [self._make_doc("충남대 도서관 (더미)", info, self.BASE_URL, now, valid, today) for info in infos]
