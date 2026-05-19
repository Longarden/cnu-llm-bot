"""질문 텍스트 → 카테고리 ID 매핑."""

CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "A_dining": ["학식", "밥", "식단", "메뉴", "식당", "점심", "저녁"],
    "A_library": ["도서관", "열람실", "대출", "좌석", "스터디룸"],
    "A_shuttle": ["셔틀", "버스", "순환버스", "교내버스"],
    "B_academic": ["수강신청", "졸업", "학점", "성적", "휴학", "복학", "수강"],
    "C_administration": ["증명서", "서류", "학생증", "등록금", "행정"],
    "D_scholarship": ["장학금", "장학", "국가장학", "근로장학"],
    "E_career": ["취업", "진로", "채용", "인턴", "현장실습"],
    "F_department": ["학과", "학부", "전공", "교수", "학과장"],
    "G_dormitory": ["기숙사", "생활관", "외박"],
    "G_student_life": ["동아리", "보건", "상담", "편의시설"],
    "H_facilities": ["위치", "건물", "시설", "헬스장", "수영장", "예약"],
    "I_international": ["교환학생", "유학", "국제", "영어강의"],
    "J_extracurricular": ["비교과", "대외활동", "봉사", "공모전", "창업"],
    "K_notices": ["공지", "공고", "알림", "안내"],
    "L_general": ["충남대", "학교 소개", "총장", "역사", "위치"],
}


def route(question: str) -> str:
    """가장 많이 매칭된 카테고리 ID 반환. 미분류는 'L_general'."""
    q = question.lower()
    scores: dict[str, int] = {cat: 0 for cat in CATEGORY_KEYWORDS}
    for cat, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in q:
                scores[cat] += 1
    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else "L_general"
