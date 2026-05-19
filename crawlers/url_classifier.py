CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "A": ["학식", "식단", "도서관", "셔틀", "버스"],
    "B": ["학사", "수강", "졸업", "학점", "성적", "일정"],
    "C": ["행정", "증명서", "민원", "서류"],
    "D": ["장학", "지원금", "등록금"],
    "E": ["취업", "진로", "채용", "인턴"],
    "F": ["학과", "학부", "전공", "교수"],
    "G": ["기숙사", "동아리", "보건", "학생생활"],
    "H": ["시설", "위치", "예약", "캠퍼스"],
    "I": ["국제", "교환학생", "유학"],
    "J": ["비교과", "대외활동", "봉사"],
    "K": ["공지", "공고", "알림"],
    "L": ["소개", "연혁", "비전", "총장"],
}


def classify_url(url: str, text: str = "") -> str:
    """URL 또는 텍스트 기반으로 카테고리 ID 반환. 미분류는 'L'."""
    combined = (url + " " + text).lower()
    for cat_id, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in combined for kw in keywords):
            return cat_id
    return "L"
