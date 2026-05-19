from datetime import datetime, timedelta
from .base import BaseCrawler
import requests
from bs4 import BeautifulSoup


class DiningCrawler(BaseCrawler):
    """카테고리 A1: 학식(식당) 메뉴 크롤러."""

    category_id = "A_dining"
    category_name = "학식"
    freshness_tier = "time_sensitive"
    BASE_URL = "https://www.cnu.ac.kr/life/restMenu.do"

    def crawl(self) -> list[dict]:
        now = datetime.utcnow().isoformat()
        valid = (datetime.utcnow() + timedelta(days=1)).isoformat()
        today = now[:10]
        try:
            resp = requests.get(self.BASE_URL, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            items = []
            for section in soup.select(".menu-section, .restaurant, table")[:10]:
                text = section.get_text(separator=" ", strip=True)
                if len(text) < 10:
                    continue
                items.append(self._make_doc("충남대 학식 메뉴", text, self.BASE_URL, now, valid, today))
            return items if items else self._fallback()
        except Exception as e:
            print(f"[dining] 크롤 실패: {e}")
            return self._fallback()

    def _fallback(self) -> list[dict]:
        now = datetime.utcnow().isoformat()
        valid = (datetime.utcnow() + timedelta(days=1)).isoformat()
        today = now[:10]
        menus = [
            "학생식당 A코너: 된장찌개, 잡채, 김치, 밥 (3,000원)",
            "학생식당 B코너: 제육볶음, 콩나물국, 깍두기, 밥 (3,500원)",
            "교직원식당: 갈비탕, 나물, 김치, 밥 (5,000원)",
            "스낵코너: 분식류 (1,500~3,000원)",
            "카페테리아: 샌드위치, 음료 (2,000~4,500원)",
        ]
        return [self._make_doc("충남대 학식 메뉴 (더미)", m, self.BASE_URL, now, valid, today) for m in menus]
