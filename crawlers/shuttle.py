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

        from .base import fetch_with_retry
        resp = fetch_with_retry(self.BASE_URL, headers=headers, timeout=20, retries=1)
        # 서버가 charset을 ISO-8859-1로 잘못 보내 모지바케가 생긴다. 실제 인코딩은 UTF-8이므로 강제 디코드.
        html = resp.content.decode("utf-8", "replace")
        soup = BeautifulSoup(html, "html.parser")

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

        # 주변지역 이동 안내(전용 셔틀 없음 - 학생들이 궁동행을 자주 물어봄)
        items.append(self._make_doc(
            "충남대 셔틀버스 주변지역 이동 안내 (궁동/유성온천/정문)",
            "궁동, 유성온천, 충남대 정문 등 학교 주변 지역으로 가는 전용 교내 셔틀버스 노선은 없습니다. "
            "교내 순환 셔틀은 대덕(유성)캠퍼스 내부를 도는 노선이고, 캠퍼스 순환 셔틀은 대덕↔보운 구간만 운행합니다.\n"
            "- 궁동: 정문 방향에서 도보권이며 시내버스 이용이 일반적입니다.\n"
            "- 유성온천역 방면: 시내버스 또는 도시철도(유성온천역) 이용을 권장합니다.\n"
            "- 충남대 정문/충남대학교입구 버스정류장(홈플러스유성점 방면): 캠퍼스 순환 셔틀이 등교 1회 경유하며, 평소에는 시내버스를 이용합니다.\n"
            "정확한 시내버스 노선/시간은 대전광역시 시내버스 정보(대중교통) 안내를 확인하세요.",
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
            ("충남대 셔틀버스 운영 기준 안내",
             "운영기준: 학기 중 평일 주간에만 운영합니다.\n"
             "미운영: 평일 야간, 주말, 공휴일, 방학, 대학수학능력시험일(오전 10시 이전) 등.\n"
             "※ 운행 시간표는 학교 사정에 따라 변경될 수 있습니다.\n"
             "※ 학사일정 변경 시 운행 기간이 변경될 수 있습니다(총학생회, 총무과 등과 협의).\n"
             "※ 천재지변, 학교행사, 교통상황, 탑승 인원 등에 따라 운행시간이 변경될 수 있으며, "
             "교통상황 등으로 전 구간 5분 내외 오차가 발생할 수 있으니 사전 대기 바랍니다.\n"
             "운행 주체: 학교버스 / 운행 노선: 교내 순환(유성·대덕캠퍼스 내), 캠퍼스 순환(대덕↔보운)"),
            ("충남대 교내순환 셔틀버스 시간표 (오전/오후 전체)",
             "교내 순환(대덕·유성캠퍼스 내) 운행 시간표\n"
             "오전(등교): 08:20(월평역 출발) → 08:30, 09:30, 09:40, 10:30, 11:30\n"
             "오후: 13:30, 14:30, 15:30, 16:30, 17:30\n"
             "첫차 08:30 / 막차 17:30, 1일 10회 운행, 학기 중 운영(총 150일).\n"
             "※ 오전(등교) 1회만 월평역 출발(정심화 국제문화회관 하차가 종점)."),
            ("충남대 교내 순환 셔틀버스 정류장 노선 (11개 정류장)",
             "교내 순환 셔틀버스 정류장 순서(등교 노선, 11개 정류장):\n"
             "① 정심화 국제문화회관 → ② 사회과학대학 입구(한누리회관 뒤) → ③ 서문(공동실험실습관 앞) "
             "→ ④ 음악 2호관 앞 → ⑤ 공동동물실험센터(회차) → ⑥ 체육관 입구 → ⑦ 예술대학 앞 "
             "→ ⑧ 도서관 앞(대학본부 옆 농대방향) → ⑨ 학생생활관 3거리 → ⑩ 농업생명과학대학 앞 "
             "→ ⑪ 동문주차장\n"
             "이후 복귀 노선: ⑫ 농업생명과학대학 앞 → ⑬ 도서관 앞(도서관삼거리 방향) → ⑭ 예술대학 앞 "
             "→ ⑮ 서문(공동실험실습관 앞) → ⑯ 사회과학대학 입구(한누리회관 뒤) → ⑰ 산학연교육연구관 앞 "
             "→ ⑱ 정심화 국제문화회관 (1일 10회 순환)."),
            ("충남대 캠퍼스 순환 셔틀버스 (대덕↔보운) 시간표 및 노선",
             "캠퍼스 순환(대덕↔보운): 1일 1회 왕복(회차), 학기 중 운영(총 150일).\n"
             "운행 시간: 08:10(대덕 출발) → 08:50(보운 회차).\n"
             "노선: ① 골프연습장 출발(08:10) → ② 중앙도서관(08:11) → ③ 산학연교육연구관(08:12) "
             "→ ④ 충남대학교입구 버스정류장(홈플러스유성점 방면)(08:13) → ⑤ 월평역(08:15) "
             "→ ⑥ 보운캠퍼스(회차, 08:50) → ⑦ 다솔아파트 건너편 → 제2학생회관 → 중앙도서관 → 골프연습장 도착."),
            ("충남대 셔틀버스 주변지역 이동 안내 (궁동/유성온천/정문)",
             "궁동, 유성온천, 충남대 정문 등 학교 주변 지역으로 가는 전용 교내 셔틀버스 노선은 없습니다. "
             "교내 순환 셔틀은 캠퍼스 내부를 도는 노선이고, 캠퍼스 순환 셔틀은 대덕↔보운 구간만 운행합니다.\n"
             "- 궁동: 정문 방향에서 도보권이며 시내버스 이용이 일반적입니다.\n"
             "- 유성온천역 방면: 시내버스 또는 도시철도(유성온천역) 이용을 권장합니다.\n"
             "- 충남대 정문/충남대학교입구 버스정류장(홈플러스유성점 방면): 캠퍼스 순환 셔틀이 등교 1회 경유하며, 평소에는 시내버스를 이용합니다.\n"
             "정확한 시내버스 노선/시간은 대전광역시 시내버스(대중교통) 정보를 확인하세요."),
            ("충남대 셔틀버스 문의",
             "담당: 총괄(5052), 총무과(배차, 운행) ☏5115\n"
             "출처: https://plus.cnu.ac.kr/html/kr/sub05/sub05_050403.html"),
        ]
        return [
            self._make_doc(title, content, self.BASE_URL, now, valid, now[:10])
            for title, content in schedules
        ]
