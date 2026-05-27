"""W3 메타데이터 가중: freshness + category 의도 매칭 → RRF 점수 조정.

기존 hybrid_retriever 의 hall/meal/date 후처리는 '필터'(컷오프)고,
이건 '소프트 가중'(랭킹 미세 조정). 다른 점수 신호와 충돌하지 않게 작은 보너스/감점만.
"""
from datetime import datetime
import re

# 질문 키워드 → 가장 잘 맞는 data_category
_CAT_KEYWORDS = {
    "A_dining":      ["학식", "메뉴", "식당", "식권", "조식", "중식", "석식", "분식", "학생회관"],
    "A_library":     ["도서관", "열람실", "대출", "반납", "스터디룸", "DB"],
    "A_shuttle":     ["셔틀", "순환버스", "버스", "정류장", "배차"],
    "B_academic":    ["졸업", "수강신청", "학점", "전공", "교양", "휴학", "복학", "재수강",
                       "학사일정", "기말고사", "중간고사", "성적", "수강편람"],
    "C_administration": ["행정", "증명서", "포털", "마이비", "신청", "양식"],
    "D_scholarship": ["장학", "장학금", "근로", "학자금"],
    "E_career":      ["취업", "채용", "공모전", "인턴", "현장실습", "Dream"],
    "F_department":  ["학과", "교수", "연구실", "전공", "교과과정"],
    "G_dormitory":   ["기숙사", "생활관", "RC", "Dorm"],
    "G_general":     [],
    "G_student_life": ["동아리", "학생회", "축제", "MT"],
    "H_facilities":  ["시설", "건물", "주차", "지도"],
    "I_international": ["국제", "교환학생", "유학", "외국인"],
    "J_extracurricular": ["비교과", "프로그램"],
    "K_notices":     ["공지", "공지사항"],
}


def _today() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")


def _detect_category(question: str) -> str | None:
    """질문에 가장 강하게 매칭되는 카테고리 1개. 매칭 안 되면 None."""
    best, best_n = None, 0
    for cat, kws in _CAT_KEYWORDS.items():
        n = sum(1 for k in kws if k in question)
        if n > best_n:
            best_n = n
            best = cat
    return best if best_n > 0 else None


def _freshness_boost(doc: dict, today: str) -> float:
    """date 기반 신선도 보너스/감점. -0.05 ~ +0.06 범위."""
    raw = (doc.get("date") or "")[:10]
    # 등록일 같은 한국어 prefix 정리
    m = re.search(r"(\d{4})[-./](\d{2})[-./](\d{2})", doc.get("date") or "")
    if m:
        raw = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    if not raw or not raw[0].isdigit():
        return 0.0
    y = raw[:4]
    if y >= today[:4]:
        return 0.06
    if y >= str(int(today[:4]) - 1):
        return 0.03
    if y <= str(int(today[:4]) - 5):
        return -0.05
    return 0.0


def _category_boost(doc: dict, target_cat: str | None) -> float:
    if not target_cat:
        return 0.0
    if doc.get("data_category") == target_cat:
        return 0.10
    return 0.0


def apply_boost(docs: list[dict], question: str) -> list[dict]:
    """rrf_score 에 freshness + category 보너스 더해서 재정렬.

    호환성: rrf_score 없는 결과(예: 단일 채널 검색)는 score 사용.
    """
    if not docs:
        return docs
    today = _today()
    target_cat = _detect_category(question)
    for d in docs:
        base = float(d.get("rrf_score") or d.get("score") or 0.0)
        boost = _freshness_boost(d, today) + _category_boost(d, target_cat)
        d["meta_boost"] = boost
        d["final_score"] = base + boost
    return sorted(docs, key=lambda x: x.get("final_score", 0.0), reverse=True)
