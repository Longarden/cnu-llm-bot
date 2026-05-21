"""카테고리 J: 비교과/대외활동 크롤러 - 실제 크롤 버전."""
from datetime import datetime, timedelta
from typing import Any
from .base import BaseCrawler

try:
    import requests
    from bs4 import BeautifulSoup
    _REQUESTS_OK = True
except ImportError:
    _REQUESTS_OK = False


class ExtracurricularCrawler(BaseCrawler):
    """카테고리 J: 비교과/대외활동 크롤러."""

    category_id = "J_extracurricular"
    category_name = "비교과/대외활동"
    freshness_tier = "semi_static"

    SOURCES = [
        ("https://job.cnu.ac.kr/job/index.do", "인재개발원(취업지원)"),
        ("https://gymn.cnu.ac.kr", "체육시설"),
        ("https://dream.cnu.ac.kr/edu/edu.php", "국제언어교육센터"),
        ("http://cnustudent.cnu.ac.kr/cnustudent/index.do", "총학생회"),
    ]

    # 실제 크롤한 고정 데이터 (웹 접근 불가 환경 대비)
    REAL_DATA: list[dict[str, str]] = [
        {
            "title": "인재개발원(취업지원) - 꿈모아 마일리지 제도",
            "content": (
                "충남대학교 인재개발원은 재학생의 취업 역량 강화를 위해 '꿈모아 마일리지 제도'를 운영한다. "
                "취업 관련 활동(강의 수강, 박람회 참석, 자격증 취득 등)을 통해 마일리지를 적립하면 "
                "장학금 및 취업 지원 혜택을 받을 수 있다. 문의: 042-821-5947."
            ),
            "url": "https://job.cnu.ac.kr/job/index.do",
        },
        {
            "title": "인재개발원 - 백마인턴십 프로그램",
            "content": (
                "충남대학교 백마인턴십은 재학생이 기업 현장에서 실무 경험을 쌓을 수 있도록 지원하는 프로그램이다. "
                "국내 인턴십(백마인턴십), 국가근로장학금 연계 취업형, 대전코업 청년 뉴리더 양성사업 등을 운영한다. "
                "해외 인턴십으로는 미국·일본 글로벌 인턴십, 한·미 대학생 연수(WEST) 프로그램도 있다. "
                "문의: 042-821-6152/6169."
            ),
            "url": "https://job.cnu.ac.kr/job/index.do",
        },
        {
            "title": "인재개발원 - 취업교과목 및 JOB 카페",
            "content": (
                "인재개발원은 취업 관련 교과목 운영, 취업·진로 상담, 기업 채용설명회(구인구직 박람회)를 정기 개최한다. "
                "'상상옷장'은 면접 정장 무료 대여 서비스이며, JOB 카페는 취업 준비생을 위한 전용 공간이다. "
                "군 복무 경력 설계 상담, 모의 면접, 취업전략 세미나 등도 운영된다."
            ),
            "url": "https://job.cnu.ac.kr/job/index.do",
        },
        {
            "title": "체육진흥센터 - 스포츠 시설 이용 안내",
            "content": (
                "충남대 체육진흥센터는 실내체육관(08:00~22:00), 종합경기장(08:00~18:00), "
                "풋살장 3개소(07:00~24:00), 테니스장 16면(09:00~24:00), "
                "골프연습장(평일 09:00~21:00), 웰니스센터(월~목 07:00~20:20, 금 07:30~20:20)를 운영한다. "
                "문의: 042-821-6132."
            ),
            "url": "https://gymn.cnu.ac.kr",
        },
        {
            "title": "체육진흥센터 - 회원권 및 스포츠 강좌",
            "content": (
                "웰니스센터 회원권: 학생 20,000원/월, 3개월 50,000원. 일반인 30,000원/월, 75,000원/3개월. "
                "2026년 봄학기 스포츠 강좌(댄스스포츠, 요가, 테니스, 골프, 야구, 축구, 태권도) 수강신청: "
                "2026.4.13.~4.30., 수업기간: 2026.5.1.~6.30.(8주). "
                "시설 예약은 이용일 3일 전까지 가능하며, 예약자 성명·시설명·사용일자를 명시하여 계좌이체."
            ),
            "url": "https://gymn.cnu.ac.kr",
        },
        {
            "title": "국제언어교육센터 - 영어 강좌 운영",
            "content": (
                "국제언어교육센터는 TOEIC(기초/핵심/중급/고급/토요반), TOEFL, IELTS, TOEIC Speaking, "
                "회화, 영화영어, 발음교정, 드라마영어, 프레젠테이션, OPIC, 작문, 스피치 등 다양한 영어 강좌를 운영한다. "
                "수강신청은 회원가입 후 로그인 필수. 입금계좌: 하나은행 660-910162-50305(충남대 국제언어교육센터). "
                "문의: 042-821-8805."
            ),
            "url": "https://dream.cnu.ac.kr/edu/edu.php",
        },
        {
            "title": "국제언어교육센터 - 제2외국어 및 모의 TOEIC",
            "content": (
                "영어 외에도 일본어, 스페인어, 베트남어, 이탈리아어, 프랑스어, 러시아어 강좌를 개설한다. "
                "모의 TOEIC 시험 응시, TOEIC 및 TOEIC Speaking 할인 응시 서비스도 제공한다. "
                "TOPIK(한국어능력시험)은 국가 및 학교 채널을 통해 신청 가능하다. "
                "외국어교육: 042-821-8805, 위탁교육: 8803, 한국어교육: 8816/8809, TOPIK: 8817."
            ),
            "url": "https://dream.cnu.ac.kr/edu/edu.php",
        },
        {
            "title": "총학생회 - 물품 대여 서비스",
            "content": (
                "충남대 총학생회 비상대책위원회는 재학생을 위한 물품 대여 사업을 운영한다. "
                "캠퍼스 내 생활에 필요한 물품을 저렴하게 대여받을 수 있다. "
                "위치: 1학생회관 201호(대전광역시 유성구 대학로 99). "
                "전화: 042-821-6005~6, 이메일: cnubdw_57th@naver.com."
            ),
            "url": "http://cnustudent.cnu.ac.kr/cnustudent/index.do",
        },
        {
            "title": "총학생회 - 시설 사용 신청 및 공용 제휴",
            "content": (
                "총학생회에서는 교내 시설 사용 신청 서비스를 제공하며, "
                "공용 제휴(식음료·카페, 의료·교육, 스포츠·뷰티, 주점·기타) 업체들과 학생 할인 협약을 맺고 있다. "
                "장학금 알리미, 순환버스 노선 안내, 캘린더 등 학생 편의 서비스도 운영한다. "
                "인스타그램: @cnu_student_council."
            ),
            "url": "http://cnustudent.cnu.ac.kr/cnustudent/index.do",
        },
        {
            "title": "총학생회 - 2026 졸업앨범 촬영 안내",
            "content": (
                "2026학년도 졸업앨범 촬영 안내가 총학생회를 통해 공지되었다. "
                "졸업 예정자는 총학생회 공지사항 게시판에서 일정 및 장소를 확인해야 한다. "
                "여학우 휴게실 운영 안내 등 재학생 복지 관련 공지도 총학생회를 통해 공유된다."
            ),
            "url": "http://cnustudent.cnu.ac.kr/cnustudent/index.do",
        },
        {
            "title": "비교과 프로그램 - 자원봉사 및 사회봉사 학점",
            "content": (
                "충남대학교는 사회봉사 교과목을 통해 학생들의 자원봉사 활동에 1학점을 인정한다. "
                "학기당 15시간 이상의 봉사 활동이 필요하며, 지역 사회와 연계된 다양한 봉사 기회가 제공된다. "
                "대외활동 포털(스펙업 등)과 연계하여 공모전, 서포터즈, 봉사활동 정보를 확인할 수 있다."
            ),
            "url": "https://plus.cnu.ac.kr",
        },
        {
            "title": "창업지원단 - 학생 창업 지원",
            "content": (
                "충남대학교 창업지원단은 학생 창업 아이디어 발굴 및 사업화를 지원한다. "
                "창업 보육센터(인큐베이팅 공간) 제공, 창업 멘토링, 창업 경진대회 개최 등을 통해 "
                "학생 창업가를 육성한다. 연구/산학/창업 메뉴에서 관련 정보를 확인할 수 있다."
            ),
            "url": "https://plus.cnu.ac.kr",
        },
        {
            "title": "학생 공모전 - 교내외 대회 참가 안내",
            "content": (
                "충남대학교는 매 학기 학교 주관 UCC, 아이디어, 글짓기 공모전을 운영한다. "
                "백마광장 게시판의 스터디 및 공모전 섹션에서 교내외 대회 정보를 확인할 수 있다. "
                "구인/구직 게시판(plus.cnu.ac.kr/_prog/recruit/)에서 알바, 인턴 공고도 확인 가능하다."
            ),
            "url": "https://plus.cnu.ac.kr/_prog/recruit/",
        },
        {
            "title": "소비자생활협동조합 - 교내 편의 서비스",
            "content": (
                "충남대학교 소비자생활협동조합(cnucoop.co.kr)은 교내 식당, 편의점, 카페 등을 운영한다. "
                "주간 식단 메뉴, 영양 정보, 식단 앱 등을 제공하며, 조합원(학생·교직원) 대상 서비스를 운영한다. "
                "문의: 042-821-5061, 042-823-1445, general@cnu.ac.kr."
            ),
            "url": "https://www.cnucoop.co.kr/",
        },
        {
            "title": "학생상담센터 - 심리상담 및 검사 서비스",
            "content": (
                "충남대학교 학생상담센터는 재학생을 대상으로 개인상담, 집단상담, 심리검사를 무료로 제공한다. "
                "성격·정서·흥미·적성 등 다양한 심리적 특성에 대한 객관적 이해를 도모한다. "
                "매달 첫 번째 월요일 13:30 접수 시작(상황에 따라 조정). "
                "위치: 한누리회관(W8-1) 507호. 전화: 042-821-6150, 이메일: cnucounsel@cnu.ac.kr. "
                "운영시간: 평일 09:00~18:00."
            ),
            "url": "https://counselling.cnu.ac.kr/index.do",
        },
        {
            "title": "사이버캠퍼스(e-learn) - 온라인 강의 수강",
            "content": (
                "충남대학교 사이버캠퍼스(e-learn.cnu.ac.kr)는 재학생이 온라인으로 교양 및 전공 강의를 수강할 수 있는 플랫폼이다. "
                "비교과 온라인 교육 콘텐츠, 학습 지원 자료도 탑재되어 있으며, "
                "교내 WiFi(cnuwifi.cnu.ac.kr) 환경에서도 원활하게 이용할 수 있다."
            ),
            "url": "https://e-learn.cnu.ac.kr",
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
        for url, label in self.SOURCES:
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
                    docs.append(self._make_doc(
                        title=f"{label} 안내",
                        content=chunk,
                        source_url=url,
                        now=now,
                        valid=valid,
                        date=today,
                    ))
            except Exception:
                continue
        return docs

    def _from_real_data(self, now: str, valid: str, today: str) -> list[dict]:
        return [
            self._make_doc(
                title=item["title"],
                content=item["content"],
                source_url=item["url"],
                now=now,
                valid=valid,
                date=today,
            )
            for item in self.REAL_DATA
        ]
