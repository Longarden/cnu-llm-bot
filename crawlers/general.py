from datetime import datetime, timedelta
from .base import BaseCrawler


class GeneralCrawler(BaseCrawler):
    """카테고리 L: 학교 일반/소개 크롤러."""

    category_id = "L_general"
    category_name = "학교 일반/소개"
    freshness_tier = "static"
    BASE_URL = "https://www.cnu.ac.kr"

    def crawl(self) -> list[dict]:
        return self._fallback()

    def _fallback(self) -> list[dict]:
        now = datetime.utcnow().isoformat()
        valid = (datetime.utcnow() + timedelta(days=30)).isoformat()
        today = now[:10]
        items = [
            "충남대학교: 1952년 설립. 대전광역시 유성구 대학로 99. 국립 종합대학.",
            "재학생 수: 약 25,000명. 교직원 약 3,500명.",
            "단과대학: 인문대, 사회과학대, 자연과학대, 공과대, 농업생명과학대, 경상대, 사범대, 의대, 수의대, 간호대 등.",
            "대학 비전: 창의·혁신·공헌을 추구하는 세계적 수준의 국립대학.",
            "총장실 위치: 대학본부(행정관) 4층. 대표전화 042-821-5114.",
            "충남대 캠퍼스: 유성 본캠퍼스 + 세종 대덕캠퍼스.",
            "이메일 형식: 학번@o.cnu.ac.kr (학생), 아이디@cnu.ac.kr (교직원).",
        ]
        return [self._make_doc("충남대 소개 (더미)", item, self.BASE_URL, now, valid, today) for item in items]
