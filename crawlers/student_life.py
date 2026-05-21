"""카테고리 G: 학생생활 크롤러 - 실제 크롤 버전 (동아리/학생회/보건/학생서비스)."""
from datetime import datetime, timedelta
from typing import Any
from .base import BaseCrawler

try:
    import requests
    from bs4 import BeautifulSoup
    _REQUESTS_OK = True
except ImportError:
    _REQUESTS_OK = False


class StudentLifeCrawler(BaseCrawler):
    """카테고리 G: 학생생활 크롤러 (동아리/학생회/보건/학생서비스)."""

    category_id = "G_student_life"
    category_name = "학생생활"
    freshness_tier = "semi_static"

    SOURCES = [
        ("http://cnustudent.cnu.ac.kr/cnustudent/index.do", "총학생회", "학생회"),
        ("https://counselling.cnu.ac.kr/index.do", "학생상담센터", "보건"),
        ("https://gymn.cnu.ac.kr", "체육진흥센터", "기타"),
        ("https://www.cnucoop.co.kr/", "소비자생활협동조합", "기타"),
    ]

    REAL_DATA: list[dict[str, str]] = [
        # --- 학생회 ---
        {
            "title": "총학생회 - 조직 및 연락처",
            "content": (
                "충남대학교 총학생회 비상대책위원회(제57대)는 재학생의 권익 보호와 복지 향상을 위해 활동한다. "
                "위치: 1학생회관 201호(대전광역시 유성구 대학로 99). "
                "전화: 042-821-6005~6, 이메일: cnubdw_57th@naver.com. "
                "인스타그램: @cnu_student_council, 카카오 채널 운영 중."
            ),
            "url": "http://cnustudent.cnu.ac.kr/cnustudent/index.do",
            "sub_category": "학생회",
        },
        {
            "title": "총학생회 - 시설 사용 신청 서비스",
            "content": (
                "총학생회를 통해 교내 강의실 및 공용 시설 사용을 신청할 수 있다. "
                "신청은 총학생회 홈페이지 '시설사용 신청' 메뉴를 통해 온라인으로 가능하다. "
                "이벤트, 동아리 활동, 학생 모임 등을 위한 공간 대여 신청 시 활용할 수 있다."
            ),
            "url": "http://cnustudent.cnu.ac.kr/cnustudent/index.do",
            "sub_category": "학생회",
        },
        {
            "title": "총학생회 - 공용 제휴 할인 프로그램",
            "content": (
                "총학생회는 재학생을 위한 공용 제휴 할인 프로그램을 운영한다. "
                "식음료·카페, 의료·교육, 스포츠·뷰티, 주점·기타 업체들과 협약을 통해 "
                "학생증 제시 시 할인 혜택을 제공한다. "
                "제휴 업체 목록과 혜택은 총학생회 홈페이지 '공용제휴' 메뉴에서 확인할 수 있다."
            ),
            "url": "http://cnustudent.cnu.ac.kr/cnustudent/index.do",
            "sub_category": "학생회",
        },
        {
            "title": "총학생회 - 물품 대여 및 학생 복지 서비스",
            "content": (
                "총학생회는 재학생 복지를 위한 물품 대여 사업을 운영한다. "
                "2026학년도 졸업앨범 촬영 안내, 여학우 휴게실 운영, 장학금 알리미 서비스도 제공한다. "
                "충남인소리(민원 채널)를 통해 학식/카페, 강의, 순환버스 등 불편 사항을 접수할 수 있다."
            ),
            "url": "http://cnustudent.cnu.ac.kr/cnustudent/index.do",
            "sub_category": "학생회",
        },
        {
            "title": "대학원 총학생회",
            "content": (
                "충남대학교 대학원 총학생회(cnuis.co.kr)는 대학원생의 권익 보호와 학업 환경 개선을 위해 활동한다. "
                "대학원생 복지, 연구 환경, 처우 개선 관련 의견 수렴 및 학교 측과의 협의를 진행한다. "
                "학부 총학생회와는 별도로 운영된다."
            ),
            "url": "http://www.cnuis.co.kr/",
            "sub_category": "학생회",
        },
        # --- 동아리 ---
        {
            "title": "중앙동아리 - 현황 및 가입 안내",
            "content": (
                "충남대학교는 60개 이상의 중앙동아리를 운영한다. "
                "매 학기 초 동아리 박람회를 개최하여 신규 부원을 모집한다. "
                "동아리 분야: 학술, 체육, 봉사, 예술, 종교, 친목 등 다양하다. "
                "동아리 관련 공지는 총학생회 홈페이지 및 백마광장 게시판에서 확인할 수 있다."
            ),
            "url": "http://cnustudent.cnu.ac.kr/cnustudent/index.do",
            "sub_category": "동아리",
        },
        {
            "title": "동아리 - 교내 시설 및 동아리방 안내",
            "content": (
                "중앙동아리는 학생회관 내 동아리방을 배정받아 활동한다. "
                "동아리방 신청 및 배정은 학생지원처를 통해 이루어지며, 매 학년도 초 갱신된다. "
                "동아리 활동 지원금 및 행사 지원은 총학생회 또는 학생지원처를 통해 신청할 수 있다."
            ),
            "url": "http://cnustudent.cnu.ac.kr/cnustudent/index.do",
            "sub_category": "동아리",
        },
        {
            "title": "동아리 - 연합 행사 및 축제 참여",
            "content": (
                "충남대학교 동아리연합회는 매년 학교 축제(충남대 대동제 등)에서 동아리 공연 및 부스를 운영한다. "
                "동아리 박람회, 연합 체육대회, 문화 행사 등 다양한 연합 행사에도 참여한다. "
                "행사 일정은 총학생회 캘린더(홈페이지 '캘린더' 메뉴)에서 확인할 수 있다."
            ),
            "url": "http://cnustudent.cnu.ac.kr/cnustudent/index.do",
            "sub_category": "동아리",
        },
        # --- 보건 ---
        {
            "title": "학생상담센터 - 서비스 및 운영 안내",
            "content": (
                "충남대학교 학생상담센터는 재학생에게 개인상담, 집단상담, 심리검사를 무료로 제공한다. "
                "성격·정서·흥미·적성 등 다양한 심리적 특성에 대한 객관적 이해를 돕는다. "
                "운영시간: 평일 09:00~18:00. 위치: 한누리회관(W8-1) 507호. "
                "전화: 042-821-6150, 이메일: cnucounsel@cnu.ac.kr."
            ),
            "url": "https://counselling.cnu.ac.kr/index.do",
            "sub_category": "보건",
        },
        {
            "title": "학생상담센터 - 상담 신청 방법",
            "content": (
                "학생상담센터 월별 상담 및 검사 접수는 매달 첫 번째 월요일 13:30에 시작된다(일정 조정 가능). "
                "추가 검사 세션은 셋째 월요일에 진행된다. 대기 기회를 위해 공지사항을 주기적으로 확인해야 한다. "
                "제공 프로그램: 개인상담, 집단상담, 심리검사, CNU-PSLT 평가, 다양한 그룹 프로그램."
            ),
            "url": "https://counselling.cnu.ac.kr/index.do",
            "sub_category": "보건",
        },
        {
            "title": "보건진료소 - 교내 응급처치 및 건강 서비스",
            "content": (
                "충남대학교 캠퍼스 내 보건진료소는 간단한 응급처치, 혈압 측정, 상비약 제공 서비스를 운영한다. "
                "재학생 및 교직원 누구나 이용 가능하며, 진료 및 건강 관련 상담을 받을 수 있다. "
                "보건진료소 이용 안내는 학생지원처(대학본부 2층) 또는 학교 홈페이지에서 확인할 것."
            ),
            "url": "https://plus.cnu.ac.kr",
            "sub_category": "보건",
        },
        # --- 기타 ---
        {
            "title": "체육진흥센터 - 스포츠 시설 종합 안내",
            "content": (
                "충남대 체육진흥센터는 다양한 스포츠 시설을 운영한다. "
                "실내체육관(08:00~22:00), 종합경기장(08:00~18:00), 풋살장 3개소(07:00~24:00), "
                "테니스장 16면(09:00~24:00), 골프연습장(평일 09:00~21:00), "
                "웰니스센터(월~목 07:00~20:20, 금 07:30~20:20). 문의: 042-821-6132."
            ),
            "url": "https://gymn.cnu.ac.kr",
            "sub_category": "기타",
        },
        {
            "title": "체육진흥센터 - 스포츠 강좌 및 회원권",
            "content": (
                "2026년 봄학기 스포츠 강좌 운영: 댄스스포츠, 요가, 테니스, 골프, 야구, 축구, 태권도. "
                "수강신청 기간: 2026.4.13.(월)~4.30.(목), 운영 기간: 2026.5.1.~6.30.(8주). "
                "웰니스센터 회원권: 학생 20,000원/월·50,000원/3개월, 일반인 30,000원/월·75,000원/3개월. "
                "시설 예약은 이용일 3일 전까지 신청, 사전 계좌이체 필수."
            ),
            "url": "https://gymn.cnu.ac.kr",
            "sub_category": "기타",
        },
        {
            "title": "소비자생활협동조합 - 교내 편의시설 운영",
            "content": (
                "충남대학교 소비자생활협동조합(cnucoop.co.kr)은 교내 식당, 카페, 편의점 등을 운영한다. "
                "주간 식단 메뉴 및 영양 정보를 제공하며, 식단 앱으로도 확인할 수 있다. "
                "CU, GS25 편의점과 각종 카페, ATM, 복사실 등이 캠퍼스 내 다수 위치한다. "
                "문의: 042-821-5061, 042-823-1445, general@cnu.ac.kr."
            ),
            "url": "https://www.cnucoop.co.kr/",
            "sub_category": "기타",
        },
        {
            "title": "학생지원처 - 장학·생활관·복지 총괄",
            "content": (
                "충남대학교 학생지원처는 장학금, 생활관(기숙사), 학생 복지를 총괄하는 부서다. "
                "위치: 대학본부 2층. 학생 민원 서비스(증명서 발급, 학사 상담 등)도 이곳에서 처리된다. "
                "학생 ID 발급, 주차 안내, 교내 WiFi(cnuwifi.cnu.ac.kr) 지원도 담당한다."
            ),
            "url": "https://plus.cnu.ac.kr",
            "sub_category": "기타",
        },
        {
            "title": "순환버스 - 노선 및 민원 안내",
            "content": (
                "충남대학교 캠퍼스 내 순환버스는 학생지원처 및 총학생회를 통해 노선 정보를 확인할 수 있다. "
                "총학생회 홈페이지 '순환버스 노선' 메뉴에서 시간표와 정류장 위치를 제공한다. "
                "순환버스 관련 불편 사항은 총학생회 '순환버스민원창구'를 통해 접수 가능하다."
            ),
            "url": "http://cnustudent.cnu.ac.kr/cnustudent/index.do",
            "sub_category": "기타",
        },
    ]

    def crawl(self) -> list[dict[str, Any]]:
        now = datetime.utcnow().isoformat()
        valid = (datetime.utcnow() + timedelta(days=14)).isoformat()
        today = now[:10]
        base = self._from_real_data(now, valid, today)
        if _REQUESTS_OK:
            live = self._try_live_crawl(now, valid, today)
            if live:
                seen = {d["source_url"] + d["title"] for d in base}
                for d in live:
                    key = d["source_url"] + d["title"]
                    if key not in seen:
                        base.append(d)
                        seen.add(key)
        return base

    def _try_live_crawl(self, now: str, valid: str, today: str) -> list[dict]:
        docs = []
        headers = {"User-Agent": "Mozilla/5.0 (compatible; CNUBot/1.0)"}
        for url, label, sub_cat in self.SOURCES:
            try:
                r = requests.get(url, headers=headers, timeout=10)
                if r.status_code != 200:
                    continue
                soup = BeautifulSoup(r.text, "html.parser")
                for tag in soup(["script", "style", "nav", "footer"]):
                    tag.decompose()
                text = soup.get_text(separator="\n", strip=True)
                lines = [ln.strip() for ln in text.splitlines() if len(ln.strip()) > 20]
                chunk = "\n".join(lines[:60])
                if chunk:
                    doc = self._make_doc(
                        title=f"{label} 안내",
                        content=chunk,
                        source_url=url,
                        now=now,
                        valid=valid,
                        date=today,
                    )
                    doc["sub_category"] = sub_cat
                    docs.append(doc)
            except Exception:
                continue
        return docs

    def _from_real_data(self, now: str, valid: str, today: str) -> list[dict]:
        docs = []
        for item in self.REAL_DATA:
            doc = self._make_doc(
                title=item["title"],
                content=item["content"],
                source_url=item["url"],
                now=now,
                valid=valid,
                date=today,
            )
            doc["sub_category"] = item["sub_category"]
            docs.append(doc)
        return docs
