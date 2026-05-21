"""충남대 셔틀버스 시간표 크롤러 - plus.cnu.ac.kr"""
from datetime import datetime, timedelta
from .base import BaseCrawler
import requests
from bs4 import BeautifulSoup


class ShuttleCrawler(BaseCrawler):
    category_id = "A_shuttle"
    category_name = "셔틀버스"
    freshness_tier = "static"
    BASE_URL = "https://plus.cnu.ac.kr/html/kr/sub05/sub05_050403.html"

    def crawl(self) -> list[dict]:
        now = datetime.utcnow().isoformat()
        # 셔틀 시간표는 학기 단위로 바뀌므로 3개월 유효
        valid = (datetime.utcnow() + timedelta(days=90)).isoformat()
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

        resp = requests.get(self.BASE_URL, timeout=15, headers=headers)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "html.parser")

        items = []

        # 본문 컨테이너 추출
        container = (
            soup.find("div", id="container")
            or soup.find("div", class_="content_wrap")
            or soup.find("div", id="content")
        )
        if not container:
            container = soup

        # nav/header 제거
        for tag in container.find_all(["nav", "header", "footer", "script", "style"]):
            tag.decompose()

        full_text = container.get_text(separator="\n", strip=True)

        # 운영 기준 안내
        import re
        operation_match = re.search(r"운영기준.{0,300}", full_text, re.DOTALL)
        if operation_match:
            items.append(self._make_doc(
                "충남대 셔틀버스 운영 기준",
                operation_match.group()[:300].strip(),
                self.BASE_URL, now, valid, now[:10]
            ))

        # 테이블에서 시간표 추출
        tables = soup.find_all("table")
        for idx, table in enumerate(tables):
            caption = table.find("caption")
            table_title = caption.get_text(strip=True) if caption else f"시간표 {idx+1}"
            rows = table.find_all("tr")
            if not rows:
                continue
            table_text = table.get_text(separator=" | ", strip=True)
            if len(table_text) < 20:
                continue
            items.append(self._make_doc(
                f"충남대 셔틀버스 {table_title}",
                f"[{table_title}]\n{table_text}",
                self.BASE_URL, now, valid, now[:10]
            ))

        # 노선별 텍스트 청크
        lines = [l.strip() for l in full_text.split("\n") if l.strip()]
        chunk = []
        chunk_title = "충남대 셔틀버스 운행 노선"
        for line in lines:
            if any(kw in line for kw in ["교내 순환", "캠퍼스 순환", "운행 노선", "운행시간", "운행 내용"]):
                if chunk:
                    items.append(self._make_doc(
                        chunk_title,
                        "\n".join(chunk),
                        self.BASE_URL, now, valid, now[:10]
                    ))
                chunk = [line]
                chunk_title = f"충남대 셔틀버스 {line[:30]}"
            else:
                chunk.append(line)
        if chunk:
            items.append(self._make_doc(
                chunk_title,
                "\n".join(chunk),
                self.BASE_URL, now, valid, now[:10]
            ))

        # 관리자 연락처
        contact_match = re.search(r"페이지 관리자.{0,200}", full_text, re.DOTALL)
        if contact_match:
            items.append(self._make_doc(
                "충남대 셔틀버스 담당 연락처",
                contact_match.group()[:200].strip(),
                self.BASE_URL, now, valid, now[:10]
            ))

        # 중복 제거
        seen = set()
        unique = []
        for item in items:
            key = item["content"][:80]
            if key not in seen and len(item["content"]) > 20:
                seen.add(key)
                unique.append(item)

        return unique if unique else self._static_fallback(now, valid)

    def _static_fallback(self, now: str, valid: str) -> list[dict]:
        """사이트 접속 불가 시 알려진 정보로 대체"""
        schedules = [
            ("충남대 교내 순환 셔틀버스 운영 안내",
             "운영기준: 학기 중 평일 주간 운영 (평일 야간, 주말, 공휴일, 방학, 수능일 오전 미운영)\n"
             "운행 주체: 학교버스\n운행 노선: 교내순환(대덕캠퍼스 내), 캠퍼스 순환(대덕↔보운)"),
            ("충남대 교내순환 셔틀버스 시간표",
             "교내 순환(대덕캠퍼스 내) 오전: 08:30, 09:30, 09:40, 10:30, 11:30\n"
             "오후: 13:30, 14:30, 15:30, 16:30, 17:30\n첫차: 08:20(월평역 출발)"),
            ("충남대 캠퍼스 순환 셔틀버스 시간표",
             "캠퍼스 순환(대덕↔보운): 08:10 골프연습장 출발 → 보운캠퍼스 회차(08:50)\n"
             "학기 중 운영(연 150일), 1일 1회 왕복"),
            ("충남대 교내 순환 셔틀버스 노선",
             "① 정심화 국제문화회관 → ② 사회과학대학 입구 → ③ 서문(공동실험실습관 앞) "
             "→ ④ 음악 2호관 앞 → ⑤ 공동동물실험센터(회차) → ⑥ 체육관 입구 "
             "→ ⑦ 예술대학 앞 → ⑧ 도서관 앞 → ⑨ 학생생활관 3거리 "
             "→ ⑩ 농업생명과학대학 앞 → ⑪ 동문주차장 (10회/일)"),
            ("충남대 셔틀버스 문의",
             "담당: 총괄(5052), 총무과(배차, 운행) ☏5115\n"
             "출처: https://plus.cnu.ac.kr/html/kr/sub05/sub05_050403.html"),
        ]
        return [
            self._make_doc(title, content, self.BASE_URL, now, valid, now[:10])
            for title, content in schedules
        ]
