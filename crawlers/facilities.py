"""카테고리 H: 캠퍼스 시설 실제 크롤러."""
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from .base import BaseCrawler

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120'
}

FACILITY_PAGES = [
    ('캠퍼스 안내', 'https://plus.cnu.ac.kr/html/kr/sub01/sub01_010801.html'),
    ('학교 소개', 'https://plus.cnu.ac.kr/html/kr/sub01/sub01_010101.html'),
    ('학교현황', 'https://plus.cnu.ac.kr/html/kr/sub01/sub01_010401.html'),
    ('조직도', 'https://plus.cnu.ac.kr/html/kr/sub01/sub01_010601.html'),
    ('학교상징', 'https://plus.cnu.ac.kr/html/kr/sub01/sub01_010501.html'),
    ('중앙도서관', 'https://library.cnu.ac.kr'),
    ('생활관(기숙사)', 'https://dorm.cnu.ac.kr'),
    ('학생처', 'https://stuserv.cnu.ac.kr'),
]

STATIC_FACILITIES = [
    {
        'title': '충남대학교 정문 및 위치',
        'content': (
            '충남대학교 주소: 대전광역시 유성구 대학로 99 (우편번호 34134).\n'
            '대전 지하철 1호선 유성온천역 하차 후 버스 이용 또는 도보 15~20분.\n'
            '대전역에서 버스 이용 시 약 40분 소요. 자가용 이용 시 주차장 이용 가능(유료).'
        ),
        'url': 'https://plus.cnu.ac.kr/html/kr/sub01/sub01_010801.html',
    },
    {
        'title': '충남대 중앙도서관 이용 안내',
        'content': (
            '중앙도서관: 캠퍼스 중앙부 위치. 지하 1층~지상 5층.\n'
            '열람실(24시간 일부 운영), 디지털자료실, 그룹스터디룸, 세미나실 운영.\n'
            '대출: 학부생 10권 2주, 대학원생 20권 4주. 홈페이지: library.cnu.ac.kr'
        ),
        'url': 'https://library.cnu.ac.kr',
    },
    {
        'title': '충남대 학생회관 및 편의시설',
        'content': (
            '학생회관: 캠퍼스 중앙광장 북쪽. 학생 식당, 카페, 동아리실, 편의점 위치.\n'
            '문화관: 공연·행사 개최 공간. 대강당 수용인원 약 1,000명.\n'
            '스포츠센터: 수영장, 헬스장, 체육관, 스쿼시장 운영. 학기당 이용권 별도 구매.'
        ),
        'url': 'https://plus.cnu.ac.kr/html/kr/sub01/sub01_010801.html',
    },
    {
        'title': '충남대 생활관(기숙사) 안내',
        'content': (
            '생활관 위치: 캠퍼스 내 북동쪽. 총 수용 인원 약 2,000명.\n'
            '입사 신청: 매 학기 개강 전 온라인 신청. 선발 기준: 거리, 성적, 소득 분위 등.\n'
            '식사 제공(식권제). 홈페이지: dorm.cnu.ac.kr'
        ),
        'url': 'https://dorm.cnu.ac.kr',
    },
    {
        'title': '충남대 캠퍼스 건물 배치',
        'content': (
            '공과대학 건물군: 캠퍼스 동쪽 구역 (33~50호관).\n'
            '인문사회 건물군: 캠퍼스 서쪽 구역 (1~15호관).\n'
            '자연과학 건물군: 캠퍼스 중앙~북쪽 구역.\n'
            '본부 건물(행정동): 정문 진입 후 중앙. 학사지원팀, 입학처, 총장실 소재.'
        ),
        'url': 'https://plus.cnu.ac.kr/html/kr/sub01/sub01_010801.html',
    },
    {
        'title': '충남대 의학캠퍼스(천안) 안내',
        'content': (
            '충남대학교 의과대학: 충청남도 천안시 소재.\n'
            '충남대학교병원(대전 본원)과 연계 운영.\n'
            '천안 캠퍼스 주소: 충남 천안시 서북구 안서동.'
        ),
        'url': 'https://plus.cnu.ac.kr/html/kr/sub01/sub01_010801.html',
    },
    {
        'title': '충남대 주요 연구시설',
        'content': (
            '첨단기술연구소, 반도체설계교육센터, AI연구센터 등 교내 연구소 다수 운영.\n'
            '산학협력관: 기업 연계 연구실 및 스타트업 지원 공간.\n'
            '동물실험동물실 별도 운영(연구용).'
        ),
        'url': 'https://plus.cnu.ac.kr',
    },
]


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


def _extract_main_text(soup: BeautifulSoup, min_len: int = 30) -> str:
    for tag in soup(['script', 'style', 'nav', 'noscript']):
        tag.decompose()
    for sel in ['#jwxe_main_content', '.cont_area', '.content_area', '.sub_content',
                 'main', 'article', '#content', '.sub-content', '.campus-info']:
        el = soup.select_one(sel)
        if el:
            text = el.get_text(separator='\n', strip=True)
            if len(text) >= min_len:
                return text
    body = soup.find('body')
    return body.get_text(separator='\n', strip=True) if body else ''


class FacilitiesCrawler(BaseCrawler):
    """카테고리 H: 캠퍼스 시설(위치/이용안내) 크롤러."""

    category_id = "H_facilities"
    category_name = "캠퍼스 시설"
    freshness_tier = "static"
    BASE_URL = "https://plus.cnu.ac.kr"

    def crawl(self) -> list[dict]:
        now = datetime.utcnow().isoformat()
        valid = (datetime.utcnow() + timedelta(days=30)).isoformat()
        today = now[:10]
        docs = []

        # Add static curated facility information
        for item in STATIC_FACILITIES:
            doc = self._make_doc(
                title=item['title'],
                content=item['content'],
                source_url=item['url'],
                now=now,
                valid=valid,
                date=today,
            )
            docs.append(doc)

        # Try to crawl live pages for additional content
        for page_title, url in FACILITY_PAGES:
            soup = _fetch_soup(url)
            if soup is None:
                continue
            text = _extract_main_text(soup)
            if len(text) < 50:
                continue
            lines = [l.strip() for l in text.splitlines() if len(l.strip()) > 15]
            chunk = []
            chunk_len = 0
            for line in lines:
                chunk.append(line)
                chunk_len += len(line)
                if chunk_len >= 500:
                    content = '\n'.join(chunk)
                    docs.append(self._make_doc(
                        title=f"충남대 {page_title}",
                        content=content,
                        source_url=url,
                        now=now,
                        valid=valid,
                        date=today,
                    ))
                    chunk = []
                    chunk_len = 0
            if chunk and chunk_len >= 30:
                docs.append(self._make_doc(
                    title=f"충남대 {page_title}",
                    content='\n'.join(chunk),
                    source_url=url,
                    now=now,
                    valid=valid,
                    date=today,
                ))

        if not docs:
            return self._fallback()
        return docs

    def _fallback(self) -> list[dict]:
        now = datetime.utcnow().isoformat()
        valid = (datetime.utcnow() + timedelta(days=30)).isoformat()
        today = now[:10]
        return [
            self._make_doc(item['title'], item['content'], item['url'], now, valid, today)
            for item in STATIC_FACILITIES
        ]
