from datetime import datetime, timedelta
from .base import BaseCrawler


class AdministrationCrawler(BaseCrawler):
    """카테고리 C: 행정/증명서 크롤러."""

    category_id = "C_administration"
    category_name = "행정/증명서"
    freshness_tier = "semi_static"
    BASE_URL = "https://www.cnu.ac.kr/administration"

    def crawl(self) -> list[dict]:
        return self._fallback()

    def _fallback(self) -> list[dict]:
        now = datetime.utcnow().isoformat()
        valid = (datetime.utcnow() + timedelta(days=14)).isoformat()
        today = now[:10]
        items = [
            "재학증명서 발급: 포털(plus.cnu.ac.kr) 또는 학생처 방문. 무인발급기 이용 가능(24시간).",
            "성적증명서 발급: 포털 온라인 발급 (영문 포함). 발급 수수료 500원/장.",
            "졸업증명서: 졸업 후 포털 또는 우편 신청. 처리 기간 3~5일.",
            "등록금 고지서: 매 학기 포털 → 등록/장학 메뉴에서 출력.",
            "학생증 발급: 입학 후 정문 학생처 방문. 재발급은 IC카드 신청서 제출.",
            "휴학/복학 서류: 학사지원과(1호관 202호) 또는 포털 온라인 처리.",
        ]
        return [self._make_doc("충남대 행정/증명서 (더미)", item, self.BASE_URL, now, valid, today) for item in items]
