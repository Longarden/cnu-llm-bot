from datetime import datetime, timedelta
from .base import BaseCrawler
import os
import re
import requests
from bs4 import BeautifulSoup


class NoticesCrawler(BaseCrawler):
    """카테고리 K: 공지사항(학사/일반/학과) 크롤러."""

    category_id = "K_notices"
    category_name = "공지사항"
    freshness_tier = "time_sensitive"

    # 충남대 공지(plus.cnu 학사/일반공지) + 컴퓨터인공지능학부 공지 4종.
    # 2026-06-02: 기존 www.cnu.ac.kr/bbs/CNU_40·60 은 404(주소변경) → plus.cnu 게시판으로 교체.
    NOTICE_SOURCES = [
        ("https://plus.cnu.ac.kr/_prog/_board/?code=sub07_0701", "https://plus.cnu.ac.kr"),  # 학사공지
        ("https://plus.cnu.ac.kr/_prog/_board/?code=sub07_0702", "https://plus.cnu.ac.kr"),  # 일반/장학공지
        ("https://computer.cnu.ac.kr/computer/notice/bachelor.do", "https://computer.cnu.ac.kr"),
        ("https://computer.cnu.ac.kr/computer/notice/notice.do", "https://computer.cnu.ac.kr"),
        ("https://computer.cnu.ac.kr/computer/notice/job.do", "https://computer.cnu.ac.kr"),
        ("https://computer.cnu.ac.kr/computer/notice/project.do", "https://computer.cnu.ac.kr"),
    ]

    # 본문 아닌 네비게이션/버튼 제목 제외
    _SKIP_TITLES = {"다음글", "이전글", "목록", "처음", "이전", "다음", "마지막", "검색", "더보기", "글쓰기"}

    # 리스트/본문 셀에서 게시일 추출용. YYYY-MM-DD / YYYY.MM.DD / YY.MM.DD 모두 허용.
    _DATE_RE = re.compile(r"(\d{2,4})[-.](\d{1,2})[-.](\d{1,2})")

    # 학부생 우선순위 키워드(학사/장학/비교과). 동일 날짜 내에서 앞으로 정렬.
    _PRIORITY_KW = ("학사", "장학", "비교과", "수강", "졸업", "등록금", "학자금",
                    "근로", "현장실습", "인턴", "교환학생", "복수전공", "성적", "휴학", "복학")

    def _parse_date(self, text: str) -> str:
        """문자열에서 날짜 1개를 뽑아 YYYY-MM-DD 로 정규화. 못 찾으면 빈 문자열."""
        if not text:
            return ""
        m = self._DATE_RE.search(text)
        if not m:
            return ""
        y, mo, d = m.group(1), m.group(2), m.group(3)
        if len(y) == 2:  # 26.06.02 -> 2026-06-02 (컴퓨터학부 게시판 형식)
            y = "20" + y
        try:
            dt = datetime(int(y), int(mo), int(d))
        except ValueError:
            return ""
        # 미래로 잘못 파싱된 값(번호/조회수 오인 등)은 버린다.
        if dt > datetime.utcnow() + timedelta(days=2):
            return ""
        return dt.strftime("%Y-%m-%d")

    def _row_date(self, row) -> str:
        """행의 모든 셀을 훑어 날짜 패턴이 fullmatch 되는 셀을 우선 채택.
        td:last-child(조회수)나 td.subject 텍스트 오인을 피한다."""
        cells = row.find_all("td")
        # 1순위: 셀 전체가 날짜인 칸(가장 신뢰도 높음)
        for td in cells:
            t = td.get_text(strip=True)
            if self._DATE_RE.fullmatch(t):
                return self._parse_date(t)
        # 2순위: 명시적 .date 클래스
        dt_tag = row.select_one("td.date, .date")
        if dt_tag:
            d = self._parse_date(dt_tag.get_text(strip=True))
            if d:
                return d
        # 3순위: 어느 셀이든 날짜 포함
        for td in cells:
            d = self._parse_date(td.get_text(strip=True))
            if d:
                return d
        return ""

    def crawl(self) -> list[dict]:  # 목록→각 글 링크 들어가서 trafilatura로 본문까지 가져옴
        from urllib.parse import urljoin
        from crawler_pipeline.body_extractor import fetch_html, fetch_body
        now = datetime.utcnow().isoformat()
        today = now[:10]
        valid = (datetime.utcnow() + timedelta(days=1)).isoformat()
        items = []
        seen_links = set()
        for url, base in self.NOTICE_SOURCES:
            try:
                # fetch_html: 인코딩 자동보정해서 목록 HTML 가져옴 (느린 plus.cnu 대비 20초)
                html = fetch_html(url, timeout=20)
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
                # 게시일: 리스트 행 셀에서 날짜 패턴 정확 추출(조회수/번호 칸 오인 방지)
                date_str = self._row_date(row)
                # 상세페이지 본문 추출(trafilatura). min_len 낮춰 짧은 공지도 본문 확보.
                body = fetch_body(link, timeout=15, min_len=20) if link else None
                if body:
                    content = f"{title}\n\n{body}"
                    # 리스트에 날짜가 없으면 상세 본문에서 보강
                    if not date_str:
                        date_str = self._parse_date(body)
                else:
                    content = title  # 제목만 폴백(본문 추출 실패)
                items.append(self._make_doc(
                    title=title,
                    content=content,
                    source_url=link or url,
                    now=now,
                    valid=valid,
                    date=date_str or today,
                ))

        if not items:
            return self._fallback()

        # 최신순 정렬 + 학부생 우선 키워드 가산(동일 날짜 내 우선). 날짜 내림차순.
        def _sort_key(doc):
            prio = 1 if any(k in doc["title"] for k in self._PRIORITY_KW) else 0
            return (doc.get("date", ""), prio)

        items.sort(key=_sort_key, reverse=True)
        return items

    def crawl_realtime(self) -> list[dict]:
        """라이브 단건 질의용 '경량' 공지 크롤(524 방지용).

        full crawl()은 게시판 6종 × 글마다 상세본문(최대 180 요청)이라 라이브엔 너무
        무거워 100초 터널 한도를 넘겨 524를 냈다. 여기서는:
          - plus.cnu 학사/일반공지 '목록 2개'만 (느린 학과서버는 라이브 경로에서 제외)
          - 상세 본문 미진입(목록의 제목+날짜+링크만) → 요청 2건
          - 타임아웃 CRAWL_TIMEOUT(기본 12초): 느린 plus.cnu 도 기다려줌. 2×12=최대 24초.
        최신순 정렬 후 상위 10건 반환. 실패 시 빈 리스트(→ 상위에서 정적 폴백).
        """
        from urllib.parse import urljoin
        from crawler_pipeline.body_extractor import fetch_html
        # (connect, read) 분리: 죽은 호스트는 4초에 포기, 느린 plus.cnu는 read 까지 대기.
        timeout = (float(os.environ.get("CRAWL_CONNECT_TIMEOUT", "4")),
                   float(os.environ.get("CRAWL_TIMEOUT", "15")))
        now = datetime.utcnow().isoformat()
        today = now[:10]
        valid = (datetime.utcnow() + timedelta(days=1)).isoformat()
        # plus.cnu 학사/일반공지만 사용(가장 신뢰·신속). 느린 computer.cnu 학과게시판은 제외.
        sources = [s for s in self.NOTICE_SOURCES if "plus.cnu.ac.kr" in s[0]]
        items = []
        seen = set()
        for url, base in sources:
            try:
                html = fetch_html(url, timeout=timeout)
                soup = BeautifulSoup(html, "html.parser")
            except Exception as e:
                print(f"[notices] (realtime) {url} 목록 실패: {e}")
                continue
            for row in soup.select("tr, .board-list li")[:20]:
                title_tag = row.select_one("td.subject a, .tit a, td a, .title a")
                if not title_tag:
                    continue
                title = title_tag.get_text(strip=True)
                if not title or len(title) < 3 or title in self._SKIP_TITLES:
                    continue
                href = title_tag.get("href", "")
                link = urljoin(url, href) if href else url
                if link in seen:
                    continue
                seen.add(link)
                date_str = self._row_date(row)
                # 본문 미진입 — 제목+날짜만으로 doc 구성(라이브 속도 확보).
                items.append(self._make_doc(
                    title=title, content=title, source_url=link,
                    now=now, valid=valid, date=date_str or today,
                ))
        if not items:
            return []  # 라이브 실패 → 상위(_live_crawl→chat_answer)에서 정적 폴백
        items.sort(
            key=lambda d: (d.get("date", ""),
                           1 if any(k in d["title"] for k in self._PRIORITY_KW) else 0),
            reverse=True,
        )
        return items[:10]

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
        docs = [
            self._make_doc(
                title=n,
                content=n,
                source_url="https://plus.cnu.ac.kr/_prog/_board/?code=sub07_0701",
                now=now,
                valid=valid,
                date=d,
            )
            for n, d in notices
        ]
        # 하드코딩 더미 → 실시간 경로가 라이브로 오인하지 않게 마킹(걸러짐).
        for doc in docs:
            doc["is_fallback"] = True
        return docs
