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

        from .base import fetch_with_retry
        # 식단은 항상 라이브 우선 경로라 타임아웃을 env(CRAWL_TIMEOUT, 기본 12초)에 맡겨
        # 시연 중 식당페이지가 느려도 한도 안에서 빠르게 포기/응답하게 한다(명시 인자 제거).
        resp = fetch_with_retry(self.BASE_URL, headers=headers)
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
        # rowspan/colspan 을 존중해 grid={(행,열):텍스트} 로 재구성한다.
        # (원인: 기존 코드는 rows[0] 와 cells 인덱스를 그대로 매핑 → rowspan(끼니 2칸)/
        #  colspan(구분 2칸)/rowspan=100 placeholder 때문에 끼니·식당·대상이 어긋나
        #  석식 누락 및 '구분/직원/학생' 잡음이 섞였음.)
        SKIP_TOKENS = {"구분", "직원", "학생", "메뉴운영내역", "", "-"}
        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")
            if not rows:
                continue

            grid: dict[tuple[int, int], str] = {}
            occupied: dict[tuple[int, int], bool] = {}
            for ri, row in enumerate(rows):
                cells = row.find_all(["th", "td"])
                ci = 0
                for cell in cells:
                    while occupied.get((ri, ci)):
                        ci += 1
                    try:
                        rs = int(cell.get("rowspan", 1) or 1)
                    except (TypeError, ValueError):
                        rs = 1
                    try:
                        cs = int(cell.get("colspan", 1) or 1)
                    except (TypeError, ValueError):
                        cs = 1
                    txt = cell.get_text(separator=" ", strip=True)
                    for dr in range(rs):
                        for dc in range(cs):
                            grid[(ri + dr, ci + dc)] = txt
                            occupied[(ri + dr, ci + dc)] = True
                    ci += cs

            if not grid:
                continue
            nrows = max(r for (r, _) in grid) + 1
            ncols = max(c for (_, c) in grid) + 1

            # 헤더(행 0)에서 식당명 매핑: 식당 본문은 col>=2 (col0/1 은 '구분').
            # 식단 테이블이 아니면(예: 안내 텍스트 테이블) col0 끼니가 없어 자연히 건너뜀.
            restaurant_by_col = {}
            for c in range(2, ncols):
                name = grid.get((0, c), "").strip()
                if name and name not in SKIP_TOKENS:
                    restaurant_by_col[c] = name
            if not restaurant_by_col:
                continue

            for ri in range(1, nrows):
                meal_type = grid.get((ri, 0), "").strip()
                target = grid.get((ri, 1), "").strip()  # 직원/학생
                if meal_type not in ("조식", "중식", "석식"):
                    continue

                for c, restaurant in restaurant_by_col.items():
                    cell_text = grid.get((ri, c), "").strip()
                    if not cell_text or cell_text in SKIP_TOKENS:
                        continue
                    label = f"{meal_type}({target})" if target else meal_type
                    if cell_text == "운영안함":
                        # 끼니 비운영도 묻기 때문에 드롭하지 않고 명시한다.
                        title = f"충남대 학식 [{date_text}] {restaurant} {label}"
                        content = f"[{date_text}] {restaurant} {label}\n비운영 (운영 안함)"
                    else:
                        title = f"충남대 학식 [{date_text}] {restaurant} {label}"
                        content = f"[{date_text}] {restaurant} {label}\n{cell_text}"
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

        # 제1학생회관 푸드코트는 이미지 메뉴라 크롤 불가 -> 고정 메뉴 하드코딩(semi_static)
        items.append(self._food_court_1())
        return items

    def _food_court_1(self) -> dict:
        """제1학생회관 푸드코트 고정 메뉴(이미지 메뉴판 전사). 일일 백반과 별개.

        가격/운영시간은 학기 단위 고정이라 semi_static. 메뉴 변경 시 수동 갱신.
        """
        now = datetime.utcnow().isoformat()
        valid = "2026-08-31T00:00:00"  # 학기 단위 유효(고정 메뉴)
        content = (
            "제1학생회관 푸드코트 메뉴 (평일 운영, 주말 운영 안함):\n"
            "[라면·간식] 운영 평일 10:00~14:00(저녁 운영 안함): "
            "라면 2,500원 / 떡만두라면 3,000원 / 해장라면 3,000원 / 치즈라면 3,000원 / "
            "부대라면 4,000원 / 김밥 3,000원 / 공기밥 500원\n"
            "[양식] 11:00~14:00(저녁 운영 안함): "
            "등심왕돈까스 5,500원 / 눈꽃치즈돈까스 6,000원 / 파채돈까스 6,000원 / "
            "돈까스&파스타 6,500원 / 닭다리살스테이크 6,000원 / 파닭스테이크 6,500원 / "
            "베이컨로제파스타 5,800원\n"
            "[스낵] 11:00~14:30(저녁 운영 안함): "
            "버터김치별달걀밥 5,600원 / 버터김치치즈알밥 6,500원 / 치즈토핑 1,000원 / "
            "소불고기토핑 2,000원 / 떡갈비토핑 1,000원 / 감자고로케토핑 1,000원 / "
            "날치알토핑 1,000원 / 구운계란토핑 500원 / 컵버터감자칩 2,000원\n"
            "[한식] 11:00~14:00, 17:00~19:00: "
            "비빔밥 7,000원 / 묵은지김치찌개 5,800원 / 부대햄플러스김치찌개 6,800원 / "
            "우삼겹된장찌개 6,600원 / 별달소고기국밥 7,000원 / 뚝배기묵달걀비빔밥 5,800원 / "
            "치즈추가 1,500원 / 구운계란 2개 1,000원 / 공기밥 500원\n"
            "[일식] 11:00~19:00: "
            "얼큰소무우동국밥 6,300원 / 매운부타동고기덮밥 7,500원 / 고소한카레덮밥 5,800원 / "
            "부타동고기덮밥 5,800원 / 치킨가라아게마요 6,500원 / 세곱배기생우동 6,500원 / "
            "매운속풀이해장우동 5,300원 / 가스오부시생우동 5,000원 / 마제소바 6,000원 / "
            "1L치킨포케샐러드 6,800원 / 1/2우동+주먹밥+가라아게4p 7,500원 / "
            "꼬지어묵2p+생우동 6,500원 / 컵가라아게4p 2,000원 / 1/2우동 3,500원 / 주먹밥 2개 1,500원\n"
            "[중식] 11:00~14:00, 16:00~19:00: "
            "차돌온면 6,500원 / 매운차돌온면 6,500원 / 온국밥 6,500원 / 매운온국밥 6,500원 / "
            "비빔면 5,800원 / 냉면 5,800원 / 공기밥 500원\n"
            "원산지: 쌀 국내산, 김치 배추(국내/중국)·고춧가루(국내/중국), 돈까스·베이컨 돼지고기(외국산), "
            "닭다리살 브라질산, 소고기 미국·호주산, 두부 콩(외국산)."
        )
        return {
            "source_url": "https://mobileadmin.cnu.ac.kr/food/index.jsp",
            "data_category": self.category_id,
            "last_crawled_at": now,
            "valid_until": valid,
            "freshness_tier": "semi_static",
            "original_text": content,
            "title": "제1학생회관 푸드코트 메뉴 (라면·양식·스낵·한식·일식·중식)",
            "content": content,
            "date": now[:10],
        }
