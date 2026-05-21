"""카테고리 I: 국제/교환 크롤러 - 실제 크롤 버전."""
from datetime import datetime, timedelta
from typing import Any
from .base import BaseCrawler

try:
    import requests
    from bs4 import BeautifulSoup
    _REQUESTS_OK = True
except ImportError:
    _REQUESTS_OK = False


class InternationalCrawler(BaseCrawler):
    """카테고리 I: 국제/교환 크롤러."""

    category_id = "I_international"
    category_name = "국제/교환"
    freshness_tier = "semi_static"

    SOURCES = [
        ("https://cnuint.cnu.ac.kr/cnuint/index.do", "국제교류본부"),
        ("https://dream.cnu.ac.kr/", "국제언어교육센터"),
    ]

    REAL_DATA: list[dict[str, str]] = [
        {
            "title": "국제교류본부 - 교환학생 파견 프로그램 개요",
            "content": (
                "충남대학교 국제교류본부(cnuint.cnu.ac.kr)는 60개국 이상의 협정 대학과 교환학생 협약을 체결하고 있다. "
                "파견 교환학생, 글로벌 인재 양성, 복수학위 프로그램(일반·3+1 형태), 해외 인턴십, 기타 프로그램을 운영한다. "
                "문의: 교환학생 담당 042-821-7048, 국제학생처 042-821-8822, 대표 042-821-5013."
            ),
            "url": "https://cnuint.cnu.ac.kr/cnuint/index.do",
        },
        {
            "title": "국제교류본부 - 2026 MEGA CNU GLOBAL 장학생 선발",
            "content": (
                "2026 MEGA CNU GLOBAL 장학생 선발 공고가 2026년 5월 13일 게시되었다. "
                "이 장학 프로그램은 해외 파견 학생을 지원하는 충남대학교의 글로벌 장학 제도이다. "
                "세부 자격 요건 및 지원 방법은 국제교류본부 공지사항(cnuint.cnu.ac.kr)에서 확인할 수 있다."
            ),
            "url": "https://cnuint.cnu.ac.kr/cnuint/index.do",
        },
        {
            "title": "국제교류본부 - 이스라엘 정부 장학금 2026-2027",
            "content": (
                "이스라엘 정부 장학금(2026-2027) 지원자를 모집한다. "
                "풀브라이트 미국 박사후 연구 프로그램(2027-2028), 일본 글로벌 현장 인턴십 H2 2026 등 "
                "다양한 국제 장학 프로그램 공고가 국제교류본부 공지사항에 게시된다. "
                "Blue Ladder 프로젝트 참가자 모집도 진행 중이다."
            ),
            "url": "https://cnuint.cnu.ac.kr/cnuint/index.do",
        },
        {
            "title": "국제교류본부 - 교환학생 지원 자격 및 절차",
            "content": (
                "교환학생 지원 자격: 학점(GPA) 2.5 이상, 외국어 능력 증빙(TOEFL, IELTS, HSK 등) 필수. "
                "매 학기 모집 공고를 통해 지원서를 접수하며, 선발 후 파견 대학에서 수학한 학점을 충남대 학점으로 인정한다. "
                "파견 중 기숙사 및 생활 지원에 대한 안내는 국제교류본부를 통해 제공된다."
            ),
            "url": "https://cnuint.cnu.ac.kr/cnuint/index.do",
        },
        {
            "title": "국제교류본부 - 복수학위 프로그램(Dual Degree)",
            "content": (
                "충남대학교는 협정 해외 대학과 복수학위 프로그램을 운영한다. "
                "일반 복수학위와 3+1(3년 국내 + 1년 해외) 형태가 있으며, "
                "졸업 시 충남대학교와 파견 대학 두 곳의 학위를 동시에 취득할 수 있다. "
                "참여 가능 대학 목록은 국제교류본부 홈페이지에서 확인 가능하다."
            ),
            "url": "https://cnuint.cnu.ac.kr/cnuint/index.do",
        },
        {
            "title": "국제교류본부 - 외국인 유학생 지원 서비스",
            "content": (
                "외국인 유학생 지원: 한국어 교육(국제언어교육센터), 버디 프로그램, 기숙사 우선 배정. "
                "비자 및 출입국 관련 안내, 보험 가입 지원, 학생 상담 서비스를 제공한다. "
                "학사 일정, 수강 신청, 장학금, 영어 강의 안내도 외국인 유학생을 위해 별도 제공된다. "
                "국제교류본부 위치: 국제언어교육센터 206호(34134 대전)."
            ),
            "url": "https://cnuint.cnu.ac.kr/cnuint/index.do",
        },
        {
            "title": "국제교류본부 - 해외 인턴십 프로그램",
            "content": (
                "충남대학교 국제교류본부는 글로벌 해외 인턴십 프로그램을 운영한다. "
                "미국, 일본 등지의 기업 및 기관에서 실무 경험을 쌓을 수 있으며, "
                "한·미 대학생 연수(WEST) 프로그램을 통한 미국 인턴십도 지원한다. "
                "인턴십 관련 문의는 인재개발원(042-821-6152/6169) 또는 국제교류본부(042-821-5013)로 가능하다."
            ),
            "url": "https://cnuint.cnu.ac.kr/cnuint/index.do",
        },
        {
            "title": "국제교류본부 - Summer/Winter 국제 프로그램",
            "content": (
                "충남대학교는 방학 중 여름/겨울 국제 프로그램을 운영한다. "
                "단기 어학연수 장학금 지원 프로그램도 매 학기 공고를 통해 모집한다. "
                "외국 대학 학생 대상 Summer/Winter School 프로그램도 충남대에서 개최된다. "
                "세부 일정 및 신청 방법은 cnuint.cnu.ac.kr 공지사항에서 확인할 것."
            ),
            "url": "https://cnuint.cnu.ac.kr/cnuint/index.do",
        },
        {
            "title": "국제언어교육센터 - 한국어 교육 프로그램",
            "content": (
                "국제언어교육센터(dream.cnu.ac.kr)는 외국인 유학생 및 한국어 학습자를 위한 한국어 정규 교육과정을 운영한다. "
                "중국어권 학습자와 비중국어권 학습자를 위한 별도 과정이 있으며, "
                "한국어능력시험(TOPIK) 응시 지원도 제공된다. "
                "한국어 교육(비중국어권): 042-821-8816, 중국어권: 042-821-8809, TOPIK: 042-821-8817."
            ),
            "url": "https://dream.cnu.ac.kr/",
        },
        {
            "title": "국제언어교육센터 - 영어 및 제2외국어 강좌",
            "content": (
                "국제언어교육센터는 TOEIC(기초/핵심/중급/고급/토요반), TOEFL, IELTS, TOEIC Speaking, "
                "영어 회화·발음·드라마·프레젠테이션·작문·스피치 강좌를 개설한다. "
                "일본어, 스페인어, 베트남어, 이탈리아어, 프랑스어, 러시아어 제2외국어 강좌도 운영한다. "
                "외국어 교육 문의: 042-821-8805. 입금계좌: 하나은행 660-910162-50305."
            ),
            "url": "https://dream.cnu.ac.kr/edu/edu.php",
        },
        {
            "title": "국제언어교육센터 - 모의 TOEIC 및 자격시험 지원",
            "content": (
                "국제언어교육센터는 재학생을 대상으로 모의 TOEIC 시험 응시 서비스를 제공한다. "
                "TOEIC 및 TOEIC Speaking 할인 응시 혜택도 있으며, "
                "TOPIK(한국어능력시험)은 국가 및 학교 채널을 통해 신청할 수 있다. "
                "위탁교육(기업·기관 대상 맞춤형 언어 교육) 문의: 042-821-8803."
            ),
            "url": "https://dream.cnu.ac.kr/",
        },
        {
            "title": "국제교류본부 - 학사 지원(수강신청·장학금·영어강의)",
            "content": (
                "국제교류본부는 외국인 유학생의 학사 지원을 위해 학사 일정 안내, 수강신청 도움, "
                "장학금 정보 제공, 영어 강의(English-medium Instruction) 목록 안내 서비스를 운영한다. "
                "캠퍼스 내 기숙사 우선 배정, 보험 가입, 학생 상담, 비자/출입국 행정 지원도 포함된다."
            ),
            "url": "https://cnuint.cnu.ac.kr/cnuint/index.do",
        },
        {
            "title": "국제교류본부 - 협정 체결 현황 및 파트너십",
            "content": (
                "충남대학교는 60개국 이상의 해외 대학 및 기관과 국제 협정을 체결하고 있다. "
                "협정 대학 목록, 글로벌화 현황, 파트너십 정보는 국제교류본부 홈페이지(cnuint.cnu.ac.kr) "
                "'About' 섹션의 '파트너십 정보'에서 확인할 수 있다."
            ),
            "url": "https://cnuint.cnu.ac.kr/cnuint/index.do",
        },
        {
            "title": "국제교류본부 - 교환학생 수학 중 생활 지원",
            "content": (
                "파견 교환학생은 수학 기간 중 현지 기숙사 또는 자취 생활을 하게 된다. "
                "충남대학교 국제교류본부는 출국 전 오리엔테이션, 현지 긴급 연락망, "
                "귀국 후 학점 인정 절차 안내 등을 지원한다. "
                "교환학생 관련 서식 및 자료는 공지사항에서 다운로드 가능하다."
            ),
            "url": "https://cnuint.cnu.ac.kr/cnuint/index.do",
        },
        {
            "title": "국제교류본부 - 취업·진로 연계 국제 프로그램",
            "content": (
                "충남대학교 국제교류본부는 JOB & Career 자료 제공, 국제 취업 설명회, "
                "글로벌 인재 양성 프로그램(Global Talent Development)을 통해 "
                "재학생의 해외 취업 역량을 강화한다. "
                "프로그램 안내 및 신청: cnuint.cnu.ac.kr 공지사항 참고."
            ),
            "url": "https://cnuint.cnu.ac.kr/cnuint/index.do",
        },
        {
            "title": "국제교류본부 - 오시는 길 및 연락처",
            "content": (
                "충남대학교 국제교류본부 위치: 국제언어교육센터(34134 대전광역시 유성구 대학로 99) 206호. "
                "대표전화: 042-821-5013. 교환학생 담당: 042-821-7048. 국제학생처: 042-821-8822. "
                "홈페이지: cnuint.cnu.ac.kr. 개인정보 처리방침 및 오시는 길 안내는 홈페이지 하단 참고."
            ),
            "url": "https://cnuint.cnu.ac.kr/cnuint/index.do",
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
