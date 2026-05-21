"""충남대 기숙사(학생생활관) 크롤러 - dorm.cnu.ac.kr"""
from datetime import datetime, timedelta
from .base import BaseCrawler
import requests
from bs4 import BeautifulSoup


class DormitoryCrawler(BaseCrawler):
    category_id = "G_dormitory"
    category_name = "기숙사"
    freshness_tier = "semi_static"
    BASE_URL = "https://dorm.cnu.ac.kr/html/kr/"
    NOTICE_URL = "https://dorm.cnu.ac.kr/_prog/_board/?code=sub03_0301&site_dvs_cd=kr&menu_dvs_cd=0302"
    MEAL_URL = "https://dorm.cnu.ac.kr/html/kr/sub04/sub04_040301.html"
    FACILITY_URL = "https://dorm.cnu.ac.kr/html/kr/sub04/sub04_040101.html"
    GUIDE_URL = "https://dorm.cnu.ac.kr/html/kr/sub04/sub04_040701.html"

    def crawl(self) -> list[dict]:
        now = datetime.utcnow().isoformat()
        valid_notice = (datetime.utcnow() + timedelta(days=7)).isoformat()
        valid_info = (datetime.utcnow() + timedelta(days=30)).isoformat()
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        items = []

        # 1. 공지사항 목록 크롤
        try:
            resp = requests.get(self.NOTICE_URL, timeout=15, headers=headers)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.content, "html.parser")

            notice_links = []
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if "mode=V" in href and "no=" in href:
                    title = a.get_text(strip=True)
                    if title and len(title) > 3:
                        if href.startswith("./?"):
                            full_url = self.NOTICE_URL.rsplit("/?", 1)[0] + "/?" + href[3:]
                        elif href.startswith("http"):
                            full_url = href
                        else:
                            full_url = "https://dorm.cnu.ac.kr/_prog/_board/" + href
                        notice_links.append((title, full_url))

            # 중복 제거
            seen_urls = set()
            unique_links = []
            for title, url in notice_links:
                if url not in seen_urls:
                    seen_urls.add(url)
                    unique_links.append((title, url))

            # 공지 상세 내용 수집 (최대 12개)
            for title, url in unique_links[:12]:
                try:
                    detail = requests.get(url, timeout=10, headers=headers)
                    detail.raise_for_status()
                    dsoup = BeautifulSoup(detail.content, "html.parser")

                    import re
                    date_match = re.search(r"\d{4}[-./]\d{2}[-./]\d{2}", dsoup.get_text())
                    date_str = date_match.group().replace(".", "-").replace("/", "-") if date_match else now[:10]

                    content_div = (
                        dsoup.find("div", class_="board_view")
                        or dsoup.find("div", class_="bbs_view")
                        or dsoup.find("div", id="view_content")
                    )
                    if content_div:
                        content_text = content_div.get_text(separator=" ", strip=True)[:600]
                    else:
                        for tag in dsoup.find_all(["nav", "header", "footer", "script", "style"]):
                            tag.decompose()
                        raw = dsoup.get_text(separator=" ", strip=True)
                        # 앞부분 nav 텍스트 제거
                        idx = raw.find(title[:10])
                        if idx > 100:
                            raw = raw[idx:]
                        content_text = raw[:600].strip()

                    if len(content_text) < 15:
                        content_text = title

                    items.append(self._make_doc(
                        f"충남대 기숙사 공지: {title}",
                        content_text,
                        url, now, valid_notice, date_str
                    ))
                except Exception as e:
                    print(f"[dormitory] 공지 상세 실패 {url}: {e}")
                    items.append(self._make_doc(
                        f"충남대 기숙사 공지: {title}",
                        title, url, now, valid_notice, now[:10]
                    ))
        except Exception as e:
            print(f"[dormitory] 공지 목록 크롤 실패: {e}")

        # 2. 식단표 페이지
        try:
            resp = requests.get(self.MEAL_URL, timeout=10, headers=headers)
            resp.raise_for_status()
            msoup = BeautifulSoup(resp.content, "html.parser")
            for tag in msoup.find_all(["nav", "header", "footer", "script", "style"]):
                tag.decompose()
            meal_text = msoup.get_text(separator="\n", strip=True)
            # 식단 관련 라인만 추출
            meal_lines = [l.strip() for l in meal_text.split("\n")
                          if len(l.strip()) > 10 and any(kw in l for kw in
                             ["식단", "조식", "중식", "석식", "메뉴", "식사", "선택식", "자율식"])]
            if meal_lines:
                items.append(self._make_doc(
                    "충남대 기숙사 식단 안내",
                    "\n".join(meal_lines[:20]),
                    self.MEAL_URL, now, valid_notice, now[:10]
                ))
            else:
                items.append(self._make_doc(
                    "충남대 기숙사 식단 안내",
                    f"기숙사 오늘의 식단: {self.MEAL_URL}\n식사 신청(자율식): http://dorm.cnu.ac.kr/freemeal/\n식사 신청(선택식): http://dorm.cnu.ac.kr/selectmeal/",
                    self.MEAL_URL, now, valid_notice, now[:10]
                ))
        except Exception as e:
            print(f"[dormitory] 식단 페이지 크롤 실패: {e}")

        # 3. 시설 안내 페이지
        try:
            resp = requests.get(self.FACILITY_URL, timeout=10, headers=headers)
            resp.raise_for_status()
            fsoup = BeautifulSoup(resp.content, "html.parser")
            for tag in fsoup.find_all(["nav", "header", "footer", "script", "style"]):
                tag.decompose()
            facility_text = fsoup.get_text(separator="\n", strip=True)
            facility_lines = [l.strip() for l in facility_text.split("\n")
                              if len(l.strip()) > 10 and any(kw in l for kw in
                                 ["피트니스", "마루나루", "세미나", "세탁", "휴게", "독서실", "시설", "편의", "닷옴"])]
            if facility_lines:
                items.append(self._make_doc(
                    "충남대 기숙사 시설 안내",
                    "\n".join(facility_lines[:15]),
                    self.FACILITY_URL, now, valid_info, now[:10]
                ))
        except Exception as e:
            print(f"[dormitory] 시설 페이지 크롤 실패: {e}")

        # 4. 입주 안내 페이지
        try:
            resp = requests.get(self.GUIDE_URL, timeout=10, headers=headers)
            resp.raise_for_status()
            gsoup = BeautifulSoup(resp.content, "html.parser")
            for tag in gsoup.find_all(["nav", "header", "footer", "script", "style"]):
                tag.decompose()
            guide_text = gsoup.get_text(separator="\n", strip=True)
            guide_lines = [l.strip() for l in guide_text.split("\n")
                           if len(l.strip()) > 10 and any(kw in l for kw in
                              ["입주", "퇴거", "신청", "합격", "안내", "규정", "생활", "절차"])]
            if guide_lines:
                items.append(self._make_doc(
                    "충남대 기숙사 입주·퇴거 안내",
                    "\n".join(guide_lines[:15]),
                    self.GUIDE_URL, now, valid_info, now[:10]
                ))
        except Exception as e:
            print(f"[dormitory] 입주 안내 페이지 크롤 실패: {e}")

        # 5. 기본 정보 (항상 포함)
        static_infos = [
            ("충남대 기숙사 기본 정보",
             "충남대학교 학생생활관은 약 5,000명 수용 규모.\n"
             "대덕관(유성 본교)과 보운관(충남대병원 위치)으로 운영.\n"
             "대표전화: 042-821-6181 | 이메일: dormitory@cnu.ac.kr\n"
             "홈페이지: https://dorm.cnu.ac.kr/html/kr/"),
            ("충남대 기숙사 신청 방법",
             "입주신청: https://dorm.cnu.ac.kr/apply/index.php\n"
             "신청 조회: https://dorm.cnu.ac.kr/html/kr/sub02/sub02_020602.html\n"
             "포털(plus.cnu.ac.kr) → 학생생활 → 학생생활관 신청"),
            ("충남대 기숙사 편의시설",
             "닷옴 피트니스(헬스장), 마루나루(스터디카페), 세미나실, 세탁실, 휴게실, 독서실 운영.\n"
             "식사 신청(자율식): http://dorm.cnu.ac.kr/freemeal/\n"
             "식사 신청(선택식): http://dorm.cnu.ac.kr/selectmeal/"),
        ]
        for title, content in static_infos:
            items.append(self._make_doc(title, content, self.BASE_URL, now, valid_info, now[:10]))

        # 중복 제거
        seen = set()
        unique = []
        for item in items:
            key = item["content"][:60]
            if key not in seen and len(item["content"]) > 10:
                seen.add(key)
                unique.append(item)

        return unique if unique else self._fallback()
