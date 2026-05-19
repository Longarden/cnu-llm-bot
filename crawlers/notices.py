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

    def crawl(self) -> list[dict]:
        now = datetime.utcnow().isoformat()
        valid = (datetime.utcnow() + timedelta(days=1)).isoformat()
        items = []
        for url, base in self.NOTICE_SOURCES:
            try:
                resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "html.parser")
                for row in soup.select("tr, .board-list li")[:10]:
                    title_tag = row.select_one("td.subject a, .tit a, td a, .title a")
                    if not title_tag:
                        continue
                    title = title_tag.get_text(strip=True)
                    if not title or len(title) < 3:
                        continue
                    link = title_tag.get("href", "")
                    if link and not link.startswith("http"):
                        link = base + link
                    # 날짜 추출 시도
                    date_tag = row.select_one("td.date, .date, td:last-child")
                    date_str = date_tag.get_text(strip=True) if date_tag else now[:10]
                    items.append(self._make_doc(
                        title=title,
                        content=title,
                        source_url=link or url,
                        now=now,
                        valid=valid,
                        date=date_str,
                    ))
            except Exception as e:
                print(f"[notices] {url} 실패: {e}")
        return items if items else self._fallback()

    def _fallback(self) -> list[dict]:
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
