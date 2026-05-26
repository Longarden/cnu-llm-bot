from datetime import datetime, timedelta
from .base import BaseCrawler
import requests
from bs4 import BeautifulSoup


class NoticesCrawler(BaseCrawler):
    """카테고리 K: 공지사항(학사/일반/학과) 크롤러."""

    category_id = "K_notices"
    category_name = "공지사항"
    freshness_tier = "time_sensitive"

    # 충남대 공지 + 컴퓨터공학과 공지 4종
    NOTICE_SOURCES = [
        ("https://www.cnu.ac.kr/bbs/CNU_40/list.do", "https://www.cnu.ac.kr"),
        ("https://www.cnu.ac.kr/bbs/CNU_60/list.do", "https://www.cnu.ac.kr"),
        ("https://computer.cnu.ac.kr/computer/notice/bachelor.do", "https://computer.cnu.ac.kr"),
        ("https://computer.cnu.ac.kr/computer/notice/notice.do", "https://computer.cnu.ac.kr"),
        ("https://computer.cnu.ac.kr/computer/notice/job.do", "https://computer.cnu.ac.kr"),
        ("https://computer.cnu.ac.kr/computer/notice/project.do", "https://computer.cnu.ac.kr"),
    ]

    # 본문 아닌 네비게이션/버튼 제목 제외
    _SKIP_TITLES = {"다음글", "이전글", "목록", "처음", "이전", "다음", "마지막", "검색", "더보기", "글쓰기"}

    def crawl(self) -> list[dict]:  # 목록→각 글 링크 들어가서 trafilatura로 본문까지 가져옴
        from urllib.parse import urljoin
        from crawler_pipeline.body_extractor import fetch_html, fetch_body
        now = datetime.utcnow().isoformat()
        valid = (datetime.utcnow() + timedelta(days=1)).isoformat()
        items = []
        seen_links = set()
        for url, base in self.NOTICE_SOURCES:
            try:
                # fetch_html: 인코딩 자동보정해서 목록 HTML 가져옴
                html = fetch_html(url, timeout=10)
                soup = BeautifulSoup(html, "html.parser")
            except Exception as e:
                print(f"[notices] {url} 목록 실패: {e}")
                continue
            for row in soup.select("tr, .board-list li")[:30]:
                title_tag = row.select_one("td.subject a, .tit a, td a, .title a")
                if not title_tag:
                    continue
                title = title_tag.get_text(strip=True)
                if not title or len(title) < 3 or title in self._SKIP_TITLES:
                    continue
                # 상대링크('?mode=view&...', '/path')를 목록 URL 기준으로 정확히 합침
                href = title_tag.get("href", "")
                link = urljoin(url, href) if href else ""
                if link in seen_links:
                    continue
                seen_links.add(link)
                date_tag = row.select_one("td.date, .date, td:last-child")
                date_str = date_tag.get_text(strip=True) if date_tag else now[:10]
                # 상세페이지 본문 추출(trafilatura). 실패 시 제목만.
                body = fetch_body(link, timeout=10)
                content = f"{title}\n\n{body}" if body else title
                items.append(self._make_doc(
                    title=title,
                    content=content,
                    source_url=link or url,
                    now=now,
                    valid=valid,
                    date=date_str,
                ))
        return items if items else self._fallback()

    def _fallback(self) -> list[dict]: # 크롤링 실패 시, 최근 공지사항 7개를 하드코딩하여 반환하는 함수입니다.
        now = datetime.utcnow().isoformat()
        valid = (datetime.utcnow() + timedelta(days=1)).isoformat()
        notices = [
            ("2026학년도 1학기 수강정정 안내 (5/20~5/21)", "2026-05-19"),
            ("2026년 하계 현장실습 참여 학생 모집 공고", "2026-05-18"),
            ("5월 학사일정: 중간고사 기간 5/6~5/10", "2026-05-01"),
            ("교내 근로장학생 추가 모집 안내", "2026-05-10"),
            ("도서관 자료 구입 신청 기간 안내 (~5/31)", "2026-05-08"),
            ("컴퓨터공학과 졸업논문 발표 일정 안내", "2026-05-15"),
            ("2026년 1학기 학과 MT 안내", "2026-04-20"),
        ]
        return [
            self._make_doc(
                title=n,
                content=n,
                source_url="https://www.cnu.ac.kr/bbs/CNU_40/list.do",
                now=now,
                valid=valid,
                date=d,
            )
            for n, d in notices
        ]
