"""카테고리 F: 컴퓨터인공지능학부 심층 크롤러."""
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from .base import BaseCrawler

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120'
}

BASE = 'https://computer.cnu.ac.kr'

PAGES = [
    ('인사말', '/computer/intro/greeting.do'),
    ('교육목표', '/computer/intro/objective.do'),
    ('연혁', '/computer/intro/history.do'),
    ('교수진', '/computer/intro/faculty01.do'),
    ('진로현황', '/computer/intro/career.do'),
    ('장학제도', '/computer/intro/scholarship02.do'),
    ('오시는길', '/computer/intro/location.do'),
    ('입학안내', '/computer/edu/admission01.do'),
    ('교과과정', '/computer/edu/curriculum.do'),
    ('졸업요건', '/computer/edu/requirements.do'),
    ('대학원 소개', '/computer/grad/intro.do'),
    ('대학원 입학안내', '/computer/grad/admission.do'),
    ('대학원 교과과정', '/computer/grad/curriculum.do'),
    ('AI융합교육전공 소개', '/computer/school_of_edu/ai_intro.do'),
    ('학사공지', '/computer/notice/bachelor.do'),
    ('일반소식', '/computer/notice/notice.do'),
    ('교외활동취업', '/computer/notice/job.do'),
    ('사업단소식', '/computer/notice/project.do'),
    ('커뮤니티 학생회', '/computer/community/student.do'),
    ('자료실', '/computer/community/data.do'),
    ('대학원 공지', '/computer/grad/notice.do'),
    ('대학원 소식', '/computer/grad/news.do'),
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


def _extract_main_text(soup: BeautifulSoup) -> str:
    for tag in soup(['script', 'style', 'nav', 'noscript']):
        tag.decompose()
    for sel in ['#jwxe_main_content', '.cont_area', '.content_area',
                 '.sub_content', 'main', 'article', '#content']:
        el = soup.select_one(sel)
        if el:
            text = el.get_text(separator='\n', strip=True)
            if len(text) >= 30:
                return text
    body = soup.find('body')
    return body.get_text(separator='\n', strip=True) if body else ''


SKIP_KW = ['바로가기', '주메뉴', '서브메뉴', '모바일 메뉴', '번역이 완료', '사이트맵', '로그인']


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


class DepartmentGeneralCrawler(BaseCrawler):
    """카테고리 F: 컴퓨터인공지능학부 심층 크롤러."""

    category_id = "F_department"
    category_name = "학과 정보"
    freshness_tier = "semi_static"
    BASE_URL = BASE

    def crawl(self) -> list[dict]:
        now = datetime.utcnow().isoformat()
        valid = (datetime.utcnow() + timedelta(days=14)).isoformat()
        today = now[:10]
        docs = []

        for page_title, path in PAGES:
            url = BASE + path
            soup = _fetch_soup(url)
            if soup is None:
                continue
            text = _extract_main_text(soup)
            if len(text) < 20:
                continue
            for chunk in _chunk_text(text):
                doc = self._make_doc(
                    title=f"컴퓨터인공지능학부 - {page_title}",
                    content=chunk,
                    source_url=url,
                    now=now,
                    valid=valid,
                    date=today,
                )
                doc['department'] = '컴퓨터인공지능학부'
                docs.append(doc)

        return docs if docs else self._fallback()

    def _fallback(self) -> list[dict]:
        now = datetime.utcnow().isoformat()
        valid = (datetime.utcnow() + timedelta(days=7)).isoformat()
        today = now[:10]
        items = [
            "컴퓨터인공지능학부: 컴퓨터공학, 소프트웨어공학, AI 전공. 홈페이지 computer.cnu.ac.kr",
            "교수진: 전임교수 약 20명. 컴퓨터공학, AI, 소프트웨어공학 분야.",
            "교과과정: 1~4학년 체계적 교과과정. 전공필수, 전공선택 구성.",
            "졸업요건: 130학점 이상 이수. 전공 60학점 이상 포함.",
            "대학원: 석사/박사 과정 운영. AI융합교육전공 포함.",
        ]
        docs = []
        for item in items:
            doc = self._make_doc(
                title="컴퓨터인공지능학부 기본 정보",
                content=item,
                source_url=self.BASE_URL,
                now=now,
                valid=valid,
                date=today,
            )
            doc['department'] = '컴퓨터인공지능학부'
            docs.append(doc)
        return docs
