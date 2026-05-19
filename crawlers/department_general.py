from datetime import datetime, timedelta
from .base import BaseCrawler


class DepartmentGeneralCrawler(BaseCrawler):
    """카테고리 F: 학과 정보 (통합 더미 크롤러)."""

    category_id = "F_department"
    category_name = "학과 정보"
    freshness_tier = "semi_static"
    BASE_URL = "https://computer.cnu.ac.kr"

    def crawl(self) -> list[dict]:
        return self._fallback()

    def _fallback(self) -> list[dict]:
        now = datetime.utcnow().isoformat()
        valid = (datetime.utcnow() + timedelta(days=7)).isoformat()
        today = now[:10]
        items = [
            "컴퓨터융합학부: 컴퓨터공학, 소프트웨어공학 전공. 홈페이지 computer.cnu.ac.kr",
            "전기·전자·통신공학부: 전기공학, 전자공학, 정보통신공학 전공.",
            "기계·메카트로닉스공학부: 기계공학, 메카트로닉스공학 전공.",
            "화학공학부: 화학공학 전공. 대전 유성캠퍼스 위치.",
            "사범대학: 교육학과, 윤리교육과, 국어교육과 등 다수 사범계열 학과.",
            "경상대학: 경영학부, 경제학과, 무역학과 등 포함.",
            "자연과학대학: 수학과, 물리학과, 화학과, 생명과학과 등.",
            "인문대학: 국어국문학과, 영어영문학과, 사학과, 철학과 등.",
            "사회과학대학: 행정학과, 사회학과, 심리학과, 언론정보학과 등.",
            "의과대학: 의학과. 대전 충남대학교병원 연계.",
        ]
        return [self._make_doc("충남대 학과 정보 (더미)", item, self.BASE_URL, now, valid, today) for item in items]
