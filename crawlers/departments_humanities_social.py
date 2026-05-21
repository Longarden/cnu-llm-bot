"""인문/사회/경상/사범 단과대학 전 학과 크롤러."""
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from pathlib import Path

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120'
}

# 실제 확인된 URL 패턴 기반으로 구성
# 인문대학: https://human.cnu.ac.kr/human/major/{key}.do
# 사회과학대학: https://socialscience.cnu.ac.kr/socsci/department/{key}.do
# 경상대학: https://cem.cnu.ac.kr/{key}
# 사범대학: https://edu.cnu.ac.kr/edu/edu/{key}.do

DEPARTMENTS = {
    '인문대학': {
        'base': 'https://human.cnu.ac.kr',
        'intro_paths': [
            '/human/intro/greeting.do',
            '/human/intro/history.do',
        ],
        'notice_path': '/human/board/notice.do',
        'depts': [
            ('국어국문학과', '/human/major/kor01.do'),
            ('영어영문학과', '/human/major/eng01.do'),
            ('독어독문학과', '/human/major/ger01.do'),
            ('불어불문학과', '/human/major/fre01.do'),
            ('중어중문학과', '/human/major/chi01.do'),
            ('일어일문학과', '/human/major/jpn01.do'),
            ('한문학과', '/human/major/chinese01.do'),
            ('사학과', '/human/major/history01.do'),
            ('국사학과', '/human/major/kor_history01.do'),
            ('철학과', '/human/major/philosophy01.do'),
            ('고고학과', '/human/major/archeology01.do'),
            ('언어학과', '/human/major/lang01.do'),
        ],
    },
    '사회과학대학': {
        'base': 'https://socialscience.cnu.ac.kr',
        'intro_paths': [
            '/socsci/intro/greeting.do',
            '/socsci/intro/history.do',
        ],
        'notice_path': '/socsci/board/notice.do',
        'depts': [
            ('사회학과', '/socsci/department/socio.do'),
            ('문헌정보학과', '/socsci/department/munhun.do'),
            ('심리학과', '/socsci/department/cnupsy.do'),
            ('언론정보학과', '/socsci/department/comm.do'),
            ('사회복지학과', '/socsci/department/welfare.do'),
            ('행정학부', '/socsci/department/cnupa.do'),
            ('정치외교학과', '/socsci/department/politics.do'),
            ('자치행정학과', '/socsci/department/autonomy.do'),
        ],
    },
    '경상대학': {
        'base': 'https://cem.cnu.ac.kr',
        'intro_paths': [
            '/cem/intro/greeting.do',
            '/cem/intro/history.do',
        ],
        'notice_path': '/cem/community/notice.do',
        'depts': [
            ('경제학과', '/economic'),
            ('경영학부', '/biz'),
            ('무역학과', '/trade'),
            ('아시아비즈니스국제학과', '/asia'),
        ],
    },
    '사범대학': {
        'base': 'https://edu.cnu.ac.kr',
        'intro_paths': [
            '/edu/intro/greetings.do',
            '/edu/intro/history.do',
            '/edu/intro/objective.do',
        ],
        'notice_path': '/edu/board/notice.do',
        'depts': [
            ('국어교육과', '/edu/edu/korean.do'),
            ('영어교육과', '/edu/edu/english.do'),
            ('교육학과', '/edu/edu/education.do'),
            ('체육교육과', '/edu/edu/sportsedu.do'),
            ('수학교육과', '/edu/edu/mathedu.do'),
            ('기술교육과', '/edu/edu/techedu.do'),
            ('음악교육과', '/edu/edu/conedu.do'),
            ('컴퓨터교육과', '/edu/edu/mmee.do'),
            ('전기전자통신교육과', '/edu/edu/eedu.do'),
            ('화학공업교육과', '/edu/edu/cnucee.do'),
        ],
    },
}

# 각 학과 개별 홈페이지 URL (사회과학대학 링크에서 확인)
DEPT_STANDALONE = {
    '사회학과': 'https://socialscience.cnu.ac.kr/socio/',
    '문헌정보학과': 'https://socialscience.cnu.ac.kr/munhun',
    '심리학과': 'https://socialscience.cnu.ac.kr/cnupsy',
    '언론정보학과': 'https://socialscience.cnu.ac.kr/comm',
    '사회복지학과': 'https://socialscience.cnu.ac.kr/welfare',
    '행정학부': 'https://socialscience.cnu.ac.kr/cnupublic',
    '정치외교학과': 'https://socialscience.cnu.ac.kr/politics/',
    '자치행정학과': 'https://socialscience.cnu.ac.kr/autonomy/',
}

SKIP_KW = ['바로가기', '주메뉴', '서브메뉴', '모바일 메뉴', '번역이 완료', '사이트맵', '로그인', '통합검색']


def _fetch_soup(url: str, timeout: int = 12) -> BeautifulSoup | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        if r.status_code != 200:
            return None
        # 인코딩 감지
        enc = r.apparent_encoding or 'utf-8'
        try:
            soup = BeautifulSoup(r.content, 'html.parser', from_encoding=enc)
        except Exception:
            soup = BeautifulSoup(r.content, 'html.parser')
        return soup
    except Exception as e:
        print(f"  [fetch오류] {url}: {type(e).__name__}")
        return None


def _extract_main_text(soup: BeautifulSoup) -> str:
    for tag in soup(['script', 'style', 'noscript']):
        tag.decompose()
    for sel in [
        '#jwxe_main_content', '.cont_area', '.content_area',
        '.sub_content', 'main', 'article', '#content',
        '.board_view', '#container', '.contents', '.wrap_content',
        '.col-lg-9', '.col-md-9',
    ]:
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
    if not lines:
        return []
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


def _make_doc(title: str, content: str, source_url: str,
              department: str, college: str,
              now: str, valid: str, today: str) -> dict:
    return {
        'source_url': source_url,
        'data_category': 'department_general',
        'last_crawled_at': now,
        'valid_until': valid,
        'freshness_tier': 'semi_static',
        'original_text': content,
        'title': title,
        'content': content,
        'date': today,
        'department': department,
        'college': college,
        'attachment_type': 'text',
    }


def _crawl_page(url: str, title: str, department: str, college: str,
                now: str, valid: str, today: str) -> list[dict]:
    soup = _fetch_soup(url)
    if soup is None:
        return []
    text = _extract_main_text(soup)
    if len(text) < 30:
        return []
    docs = []
    for chunk in _chunk_text(text):
        docs.append(_make_doc(title, chunk, url, department, college, now, valid, today))
    return docs


def crawl_all(now: str, valid: str, today: str) -> tuple[list[dict], dict]:
    all_docs = []
    summary = {}

    for college, info in DEPARTMENTS.items():
        print(f'\n=== {college} 크롤링 시작 ===')
        base = info['base']
        college_docs = []
        college_summary = {}

        # 단과대학 소개 페이지
        for path in info.get('intro_paths', []):
            url = base + path
            docs = _crawl_page(url, f'{college} - 대학소개', college, college, now, valid, today)
            college_docs.extend(docs)

        # 공지사항
        notice_path = info.get('notice_path')
        if notice_path:
            url = base + notice_path
            docs = _crawl_page(url, f'{college} - 공지사항', college, college, now, valid, today)
            college_docs.extend(docs)

        # 각 학과 페이지
        for dept_name, dept_path in info['depts']:
            dept_docs = []

            # 학과 경로가 절대 URL인지 상대 경로인지 확인
            if dept_path.startswith('http'):
                dept_url = dept_path
            else:
                dept_url = base + dept_path

            # 학과 메인 페이지
            docs = _crawl_page(dept_url, f'{dept_name} - 학과소개', dept_name, college, now, valid, today)
            dept_docs.extend(docs)

            # 추가 서브페이지 시도 (교수진, 공지)
            for sub in ['/faculty.do', '/professor.do', '/intro.do', '/notice.do']:
                sub_url = dept_url.rstrip('/') + sub
                if not sub_url.startswith('http'):
                    sub_url = base + dept_path.rstrip('/') + sub
                docs2 = _crawl_page(sub_url, f'{dept_name} - {sub.replace(".do","").strip("/")}',
                                    dept_name, college, now, valid, today)
                dept_docs.extend(docs2)

            # 단독 홈페이지가 있는 경우 추가 크롤
            standalone = DEPT_STANDALONE.get(dept_name)
            if standalone:
                docs3 = _crawl_page(standalone, f'{dept_name} - 홈페이지',
                                    dept_name, college, now, valid, today)
                dept_docs.extend(docs3)

            college_docs.extend(dept_docs)
            college_summary[dept_name] = len(dept_docs)
            print(f'  [{college}] {dept_name}: {len(dept_docs)} 청크')

        all_docs.extend(college_docs)
        summary[college] = college_summary
        print(f'  => {college} 소계: {len(college_docs)} 청크')

    return all_docs, summary


def main():
    now = datetime.utcnow().isoformat()
    valid = (datetime.utcnow() + timedelta(days=14)).isoformat()
    today = now[:10]

    all_docs, summary = crawl_all(now, valid, today)

    out_path = Path('C:/Users/dmsak/cnu-llm-bot/data/crawled/departments_humanities_social.json')
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(all_docs, f, ensure_ascii=False, indent=2)

    print(f'\n=== 크롤링 완료 ===')
    print(f'총 청크: {len(all_docs)}')
    print(f'저장 경로: {out_path}')
    total_depts = 0
    for college, dept_map in summary.items():
        print(f'\n{college}:')
        for dept_name, cnt in dept_map.items():
            print(f'  {dept_name}: {cnt} 청크')
            total_depts += 1
    print(f'\n총 학과 수: {total_depts}')
    return all_docs, summary, str(out_path)


if __name__ == '__main__':
    main()
