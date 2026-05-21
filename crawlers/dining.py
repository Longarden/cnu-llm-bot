"""충남대 학식 메뉴 크롤러 - mobileadmin.cnu.ac.kr/food/index.jsp"""
from datetime import datetime, timedelta
from .base import BaseCrawler
import requests
from bs4 import BeautifulSoup


class DiningCrawler(BaseCrawler):
    category_id = "A_dining"
    category_name = "학식"
    freshness_tier = "time_sensitive"
    BASE_URL = "https://mobileadmin.cnu.ac.kr/food/index.jsp"

    def crawl(self) -> list[dict]:
        now = datetime.utcnow().isoformat()
        valid = (datetime.utcnow() + timedelta(days=1)).isoformat()
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

        resp = requests.get(self.BASE_URL, timeout=15, headers=headers)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "html.parser")

        items = []
        # 요일별 식단 탭에서 날짜 추출
        date_text = ""
        date_btn = soup.find("button", class_="on") or soup.find("a", class_="on")
        if date_btn:
            date_text = date_btn.get_text(strip=True)
        if not date_text:
            # 페이지 내 날짜 패턴 찾기
            import re
            m = re.search(r"\d{4}\.\d{2}\.\d{2}", soup.get_text())
            date_text = m.group() if m else now[:10]

        # 식단 테이블 파싱
        tables = soup.find_all("table")
        for table in tables:
            caption = table.find("caption")
            caption_text = caption.get_text(strip=True) if caption else ""

            rows = table.find_all("tr")
            if not rows:
                continue

            # 헤더에서 식당명 추출
            headers_row = rows[0].find_all(["th", "td"])
            restaurant_names = [th.get_text(strip=True) for th in headers_row]

            meal_type = ""
            for row in rows[1:]:
                cells = row.find_all(["th", "td"])
                if not cells:
                    continue
                first = cells[0].get_text(strip=True)
                # 조식/중식/석식 구분
                if first in ["조식", "중식", "석식"]:
                    meal_type = first
                    continue

                for i, cell in enumerate(cells):
                    cell_text = cell.get_text(separator=" ", strip=True)
                    if not cell_text or cell_text in ["운영안함", "-", ""]:
                        continue
                    restaurant = restaurant_names[i] if i < len(restaurant_names) else f"식당{i}"
                    title = f"충남대 학식 [{date_text}] {restaurant} {meal_type}"
                    content = f"[{date_text}] {restaurant} {meal_type}\n{cell_text}"
                    items.append(self._make_doc(title, content, self.BASE_URL, now, valid, date_text))

        # 원재료 정보도 추가
        full_text = soup.get_text(separator="\n", strip=True)
        import re
        origin_match = re.search(r"구내식당 식재료 원산지.{0,500}", full_text, re.DOTALL)
        if origin_match:
            origin_text = origin_match.group()[:400]
            items.append(self._make_doc(
                "충남대 구내식당 식재료 원산지",
                origin_text,
                self.BASE_URL, now, valid, now[:10]
            ))

        # 운영안내 텍스트
        info_match = re.search(r"교직원과 학생 여러분들.{0,300}", full_text, re.DOTALL)
        if info_match:
            items.append(self._make_doc(
                "충남대 구내식당 운영안내",
                info_match.group()[:300],
                self.BASE_URL, now, valid, now[:10]
            ))

        if not items:
            # 페이지 전체 텍스트를 청크로 저장
            text = full_text
            chunk_size = 400
            for i in range(0, min(len(text), chunk_size * 20), chunk_size):
                chunk = text[i:i + chunk_size].strip()
                if len(chunk) < 30:
                    continue
                items.append(self._make_doc(
                    f"충남대 학식 메뉴 정보 {i // chunk_size + 1}",
                    chunk, self.BASE_URL, now, valid, now[:10]
                ))

        return items
