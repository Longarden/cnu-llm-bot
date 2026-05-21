"""충남대 도서관 크롤러 - library.cnu.ac.kr"""
from datetime import datetime, timedelta
from .base import BaseCrawler
import requests
from bs4 import BeautifulSoup


class LibraryCrawler(BaseCrawler):
    category_id = "A_library"
    category_name = "도서관"
    freshness_tier = "semi_static"
    BASE_URL = "https://library.cnu.ac.kr"
    NOTICE_LIST_URL = "https://library.cnu.ac.kr/bbs/list/1"

    def crawl(self) -> list[dict]:
        now = datetime.utcnow().isoformat()
        valid_notice = (datetime.utcnow() + timedelta(days=7)).isoformat()
        valid_hours = (datetime.utcnow() + timedelta(days=30)).isoformat()
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        items = []

        # 1. 메인 페이지에서 운영시간 및 공지 목록 수집
        resp = requests.get(self.BASE_URL, timeout=15, headers=headers)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "html.parser")

        # 운영시간 파싱
        hours_div = soup.find("div", class_="openHours") or soup.find("div", class_="open_hours")
        if hours_div:
            hours_text = hours_div.get_text(separator="\n", strip=True)
            items.append(self._make_doc(
                "충남대 도서관 운영시간",
                hours_text,
                self.BASE_URL, now, valid_hours, now[:10]
            ))
        else:
            # 텍스트에서 운영시간 패턴 찾기
            import re
            full = soup.get_text(separator="\n", strip=True)
            hours_match = re.search(r"(자유열람실|열람실|운영시간).{0,600}", full, re.DOTALL)
            if hours_match:
                items.append(self._make_doc(
                    "충남대 도서관 운영시간",
                    hours_match.group()[:600].strip(),
                    self.BASE_URL, now, valid_hours, now[:10]
                ))

        # 메인 페이지 공지 링크 수집 - URL 기준으로 중복 제거
        seen_urls = set()
        unique_links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/bbs/content/" in href:
                full_url = href if href.startswith("http") else self.BASE_URL + href
                if full_url not in seen_urls:
                    seen_urls.add(full_url)
                    text = a.get_text(strip=True)
                    # 제목이 없는 링크는 URL에서 ID 추출
                    if not text or len(text) < 3:
                        text = f"도서관 공지 {href.split('/')[-1]}"
                    unique_links.append((text[:80], full_url))

        # 2. 공지사항 상세 페이지 크롤 (최대 20개)
        for title, url in unique_links[:20]:
            try:
                detail_resp = requests.get(url, timeout=10, headers=headers)
                detail_resp.raise_for_status()
                detail_soup = BeautifulSoup(detail_resp.content, "html.parser")

                # 날짜 추출
                import re
                date_match = re.search(r"\d{4}[-./]\d{2}[-./]\d{2}", detail_soup.get_text())
                date_str = date_match.group().replace(".", "-").replace("/", "-") if date_match else now[:10]

                # 본문 추출 - library.cnu.ac.kr 구조: div.boardContent
                content_div = (
                    detail_soup.find("div", class_="boardContent")
                    or detail_soup.find("div", id="divContent")
                    or detail_soup.find("div", class_="boardDetail")
                    or detail_soup.find("div", class_="board_view")
                    or detail_soup.find("div", class_="bbs_view")
                )
                # 제목/날짜 정보
                info_div = detail_soup.find("div", class_="boardInfo") or detail_soup.find("div", class_="writeInfo")
                info_text = info_div.get_text(separator=" ", strip=True) if info_div else ""

                if content_div:
                    content_text = (info_text + " " + content_div.get_text(separator=" ", strip=True)).strip()
                else:
                    for tag in detail_soup.find_all(["nav", "header", "footer", "script", "style"]):
                        tag.decompose()
                    content_text = detail_soup.get_text(separator=" ", strip=True)
                    if len(content_text) > 300:
                        content_text = content_text[400:]

                content_text = content_text.strip()[:800]
                if len(content_text) < 20:
                    content_text = title

                items.append(self._make_doc(
                    f"충남대 도서관 공지: {title}",
                    content_text,
                    url, now, valid_notice, date_str
                ))
            except Exception as e:
                print(f"[library] 공지 상세 크롤 실패 {url}: {e}")
                items.append(self._make_doc(
                    f"충남대 도서관 공지: {title}",
                    title,
                    url, now, valid_notice, now[:10]
                ))

        # 3. 도서관 기본 서비스 정보 (메인 페이지 텍스트)
        for tag in soup.find_all(["nav", "header", "footer", "script", "style"]):
            tag.decompose()
        main_text = soup.get_text(separator="\n", strip=True)
        lines = [l.strip() for l in main_text.split("\n") if len(l.strip()) > 15]

        service_keywords = ["대출", "반납", "열람", "좌석", "스터디룸", "상호대차", "전자", "원문", "앱", "모바일"]
        service_lines = [l for l in lines if any(kw in l for kw in service_keywords)]
        if service_lines:
            items.append(self._make_doc(
                "충남대 도서관 서비스 안내",
                "\n".join(service_lines[:20]),
                self.BASE_URL, now, valid_hours, now[:10]
            ))

        # 4. 연락처 정보
        contact_info = (
            "충남대학교 중앙도서관 연락처\n"
            "중앙도서관: (042) 821-6023\n"
            "의학도서관: (042) 580-8156\n"
            "법학도서관: (042) 821-8502\n"
            "홈페이지: https://library.cnu.ac.kr"
        )
        items.append(self._make_doc(
            "충남대 도서관 연락처",
            contact_info,
            self.BASE_URL, now, valid_hours, now[:10]
        ))

        # 중복 제거 (source_url 기준)
        seen = set()
        unique = []
        for item in items:
            key = item["source_url"] + item["title"]
            if key not in seen and len(item["content"]) > 10:
                seen.add(key)
                unique.append(item)

        return unique if len(unique) >= 3 else self._library_static_fallback(now, valid_hours)

    def _library_static_fallback(self, now: str, valid: str) -> list[dict]:
        infos = [
            ("충남대 중앙도서관 운영시간",
             "자유열람실(1층): 매일 06:00~23:00\n열람실(B1~B2층, 2층): 매일 06:00~23:00\n"
             "자료실(4~5층): 평일 09:00~18:00\n연속간행물실·학위논문실(3층): 평일 09:00~18:00"),
            ("충남대 도서관 분관 운영시간",
             "의학도서관: 평일 09:00~18:00 (공휴일 휴실)\n법학도서관: 평일 09:00~18:00 (공휴일 휴실)"),
            ("충남대 도서관 대출 규정",
             "학부생: 10권(14일), 대학원생: 20권(30일)\n상호대차 서비스: 타 대학 도서 신청 가능, 보통 3~5일 소요"),
            ("충남대 도서관 좌석 예약",
             "열람실 좌석 예약: 도서관 홈페이지(library.cnu.ac.kr) 또는 모바일 앱에서 가능\n"
             "스터디룸 예약: 4인실, 8인실 운영. 하루 전 온라인 예약 필수"),
            ("충남대 도서관 연락처",
             "중앙도서관: (042) 821-6023\n의학도서관: (042) 580-8156\n법학도서관: (042) 821-8502"),
        ]
        return [
            self._make_doc(title, content, self.BASE_URL, now, valid, now[:10])
            for title, content in infos
        ]
