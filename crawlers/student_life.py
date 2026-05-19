from datetime import datetime, timedelta
from .base import BaseCrawler


class StudentLifeCrawler(BaseCrawler):
    """카테고리 G2-G4: 동아리/보건/학생지원 크롤러."""

    category_id = "G_student_life"
    category_name = "학생생활"
    freshness_tier = "semi_static"
    BASE_URL = "https://www.cnu.ac.kr/student"

    def crawl(self) -> list[dict]:
        return self._fallback()

    def _fallback(self) -> list[dict]:
        now = datetime.utcnow().isoformat()
        valid = (datetime.utcnow() + timedelta(days=14)).isoformat()
        today = now[:10]
        items = [
            "중앙동아리: 60개 이상 운영. 매 학기 초 동아리 박람회에서 모집.",
            "학생상담센터: 심리상담, 집단상담, 심리검사 무료 제공. 상담 예약 전화 042-821-7046.",
            "보건센터: 캠퍼스 내 보건진료소 운영. 간단한 응급처치, 혈압측정, 상비약 제공.",
            "학생지원처: 장학, 생활관, 학생복지 총괄. 위치 대학본부 2층.",
            "학생식당 외 편의시설: 편의점(CU, GS25), 카페, ATM, 복사실 캠퍼스 내 다수.",
        ]
        return [self._make_doc("충남대 학생생활 (더미)", item, self.BASE_URL, now, valid, today) for item in items]
