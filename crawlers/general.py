"""카테고리 G: 충남대 학교 소개/연혁/비전 실제 크롤러."""
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from .base import BaseCrawler

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120'
}

GENERAL_PAGES = [
    ('교육이념', 'https://plus.cnu.ac.kr/html/kr/sub01/sub01_010101.html'),
    ('연혁', 'https://plus.cnu.ac.kr/html/kr/sub01/sub01_0102.html'),
    ('총장 인사말', 'https://plus.cnu.ac.kr/html/kr/sub01/sub01_010301.html'),
    ('학교현황', 'https://plus.cnu.ac.kr/html/kr/sub01/sub01_010401.html'),
    ('학교상징', 'https://plus.cnu.ac.kr/html/kr/sub01/sub01_010501.html'),
    ('조직도', 'https://plus.cnu.ac.kr/html/kr/sub01/sub01_010601.html'),
]

STATIC_GENERAL = [
    {
        'title': '충남대학교 개요',
        'content': (
            '충남대학교(Chungnam National University, CNU)는 1952년 개교한 대전광역시 소재 국립대학교.\n'
            '유성구 대학로 99 위치. 대전·세종·충청권 대표 국립 거점대학.\n'
            '재학생 약 22,000명, 교직원 약 2,000명. 15개 단과대학, 100개 이상의 학과 운영.'
        ),
        'url': 'https://plus.cnu.ac.kr/html/kr/sub01/sub01_010101.html',
    },
    {
        'title': '충남대학교 교육이념 및 비전',
        'content': (
            '교육이념: 진리, 창조, 봉사.\n'
            '비전: THE STRONG CNU - 미래 사회를 선도할 강한 대학.\n'
            '핵심 가치: 연구 중심 교육, 지역 사회 기여, 글로벌 경쟁력 강화.\n'
            '주요 목표: 세계 100위권 대학 진입, 취업률 향상, 창업 생태계 구축.'
        ),
        'url': 'https://plus.cnu.ac.kr/html/kr/sub01/sub01_010101.html',
    },
    {
        'title': '충남대학교 연혁',
        'content': (
            '1952년 충남대학교 개교 (문리과대학, 농과대학으로 출발).\n'
            '1968년 종합대학교로 승격.\n'
            '1980년대~1990년대: 공과대학, 의과대학 등 단과대학 확장.\n'
            '2000년대: 연구중심대학 지정, BK21 사업 지속 참여.\n'
            '2010년대: 글로컬 대학 추진, 세종 캠퍼스 운영.\n'
            '2020년대: THE STRONG CNU 비전 선포, AI·반도체 분야 특성화.'
        ),
        'url': 'https://plus.cnu.ac.kr/html/kr/sub01/sub01_0102.html',
    },
    {
        'title': '충남대학교 단과대학 구성',
        'content': (
            '인문대학, 사회과학대학, 자연과학대학, 공과대학, 농업생명과학대학,\n'
            '경상대학, 사범대학, 의과대학, 치과대학, 수의과대학, 약학대학,\n'
            '생활과학대학, 예술대학, 자유전공학부, 창의융합학부 등 총 15개 단과대학 운영.\n'
            '대학원: 일반대학원, 교육대학원, 경영대학원, 산업대학원 등.'
        ),
        'url': 'https://plus.cnu.ac.kr/html/kr/sub01/sub01_010401.html',
    },
    {
        'title': '충남대학교 학교상징',
        'content': (
            '교화: 목련 (순결, 보람, 자연의 조화를 상징).\n'
            '교목: 느티나무 (학문의 성장과 풍요를 상징).\n'
            '교조: 독수리 (자유, 도전, 웅지를 상징).\n'
            '교색: 청색(Blue) - CNU 아이덴티티 컬러.\n'
            '마스코트: 충이와 남이 (충남대 캐릭터).'
        ),
        'url': 'https://plus.cnu.ac.kr/html/kr/sub01/sub01_010501.html',
    },
    {
        'title': '충남대학교 입학 및 모집 안내',
        'content': (
            '수시모집: 매년 9월 원서접수. 학생부종합, 학생부교과, 논술 등 전형.\n'
            '정시모집: 매년 12월 말~1월 초 원서접수. 수능 성적 반영.\n'
            '외국인 특별전형 별도 운영.\n'
            '입학 관련 문의: 충남대 입학처 (042-821-5001~5005).\n'
            '홈페이지: ipsi.cnu.ac.kr'
        ),
        'url': 'https://plus.cnu.ac.kr',
    },
    {
        'title': '충남대학교 주요 연구 및 사업',
        'content': (
            'BK21 FOUR 사업: 다수 학과 선정, 연구 역량 강화.\n'
            '반도체 특성화 사업: 전자공학과 중심 반도체 인력 양성.\n'
            'LINC 3.0 사업: 산학협력 강화.\n'
            'RIS 사업: 지역 혁신 체계 구축.\n'
            '글로컬대학30: 지역 대학 활성화 프로젝트 참여.'
        ),
        'url': 'https://plus.cnu.ac.kr',
    },
    {
        'title': '충남대학교 국제교류',
        'content': (
            '해외 협정 대학: 50개국 300개 이상 대학과 교류 협정 체결.\n'
            '교환학생 파견 및 유치 프로그램 운영.\n'
            '외국인 유학생 약 1,500명 재학.\n'
            '국제처 문의: 042-821-5085\n'
            '글로벌교육원 운영: 한국어 교육 및 외국인 지원.'
        ),
        'url': 'https://plus.cnu.ac.kr',
    },
]

SKIP_KW = ['바로가기', '주메뉴', '서브메뉴', '모바일 메뉴', '번역이 완료', '사이트맵', '로그인', '본문']


def _fetch_soup(url: str, timeout: int = 12) -> BeautifulSoup | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        if r.status_code != 200:
            return None
        soup = BeautifulSoup(r.content, 'html.parser')
        meta = soup.find('meta', attrs={'http-equiv': lambda x: x and x.lower() == 'content-type'})
        enc = 'utf-8'
        if meta and 'charset=' in meta.get('content', ''):
            enc = meta['content'].split('charset=')[-1].strip()
        return BeautifulSoup(r.content, 'html.parser', from_encoding=enc)
    except Exception:
        return None


def _extract_main_text(soup: BeautifulSoup) -> str:
    for tag in soup(['script', 'style', 'nav', 'noscript']):
        tag.decompose()
    for sel in ['.sub_content_wrap', '.cont_area', '.content_area',
                 '#content', 'main', 'article', '.sub-content', '#jwxe_main_content']:
        el = soup.select_one(sel)
        if el:
            text = el.get_text(separator='\n', strip=True)
            if len(text) >= 30:
                return text
    body = soup.find('body')
    return body.get_text(separator='\n', strip=True) if body else ''


def _chunk_text(text: str, chunk_size: int = 400) -> list[str]:
    lines = [l.strip() for l in text.splitlines() if len(l.strip()) > 10]
    lines = [l for l in lines if not any(kw in l for kw in SKIP_KW)]
    chunks = []
    buf = []
    buf_len = 0
    for line in lines:
        buf.append(line)
        buf_len += len(line)
        if buf_len >= chunk_size:
            chunks.append('\n'.join(buf))
            buf = []
            buf_len = 0
    if buf and buf_len >= 20:
        chunks.append('\n'.join(buf))
    return chunks


class GeneralCrawler(BaseCrawler):
    """카테고리 G: 학교 소개/연혁/비전 크롤러."""

    category_id = "G_general"
    category_name = "학교 일반"
    freshness_tier = "static"
    BASE_URL = "https://plus.cnu.ac.kr"

    def crawl(self) -> list[dict]:
        now = datetime.utcnow().isoformat()
        valid = (datetime.utcnow() + timedelta(days=30)).isoformat()
        today = now[:10]
        docs = []

        # Curated static content first (guaranteed)
        for item in STATIC_GENERAL:
            docs.append(self._make_doc(
                title=item['title'],
                content=item['content'],
                source_url=item['url'],
                now=now,
                valid=valid,
                date=today,
            ))

        # Live crawl of plus.cnu.ac.kr pages
        for page_title, url in GENERAL_PAGES:
            soup = _fetch_soup(url)
            if soup is None:
                continue
            text = _extract_main_text(soup)
            if len(text) < 50:
                continue
            for chunk in _chunk_text(text):
                docs.append(self._make_doc(
                    title=f"충남대 {page_title}",
                    content=chunk,
                    source_url=url,
                    now=now,
                    valid=valid,
                    date=today,
                ))

        return docs if docs else self._fallback()

    def _fallback(self) -> list[dict]:
        now = datetime.utcnow().isoformat()
        valid = (datetime.utcnow() + timedelta(days=30)).isoformat()
        today = now[:10]
        return [
            self._make_doc(item['title'], item['content'], item['url'], now, valid, today)
            for item in STATIC_GENERAL
        ]
