"""W3 메타데이터 가중: freshness + category + 변경키워드 → RRF 점수 조정.

기존 hybrid_retriever 의 hall/meal/date 후처리는 '필터'(컷오프)고,
이건 '소프트 가중'(랭킹 미세 조정). 다른 점수 신호와 충돌하지 않게 작은 보너스/감점만.

[보정 근거 — 2026-06-09]
RRF 점수는 _rrf_score=1/(60+rank) → 1위 0.0167, 양쪽 1위라도 합 0.033이 최대다.
따라서 boost 가 RRF 스케일(±0.005~0.015)을 넘으면 BM25+dense 관련도를 압도해
'카테고리/연도로만 정렬'되는 랭킹 붕괴가 난다(구버전 category+0.10·freshness+0.06 = 최대의 3배).
→ 모든 boost 를 RRF 스케일로 축소하고, freshness 는 연(year)이 아니라 '일(day) 감쇠'로 바꿨다.
또 '변동/변경/이후' 질의일 때만 변경키워드(정정·연기·임시공휴일 등) 문서를 소폭 끌어올린다.
"""
from __future__ import annotations
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


# 질의가 '변동/최신성'을 묻는 신호(이때만 변경키워드 문서를 끌어올림).
_CHANGE_Q_RE = re.compile(r"(변동|변경|바뀐|바뀌|달라진|새로|갱신|업데이트|이후|최신|최근)")

# 문서가 '실제 변경 공지'임을 시사하는 키워드(제목/본문).
_CHANGE_DOC_KW = ("변경", "정정", "연기", "취소", "변동", "임시공휴일", "단축수업",
                  "휴강", "보강", "일정 변경", "재공지", "추가 안내")


def _today_dt() -> datetime:
    return datetime.utcnow()


def _detect_category(question: str) -> "str | None":
    """질문에 가장 강하게 매칭되는 카테고리 1개. 매칭 안 되면 None."""
    best, best_n = None, 0
    for cat, kws in _CAT_KEYWORDS.items():
        n = sum(1 for k in kws if k in question)
        if n > best_n:
            best_n = n
            best = cat
    return best if best_n > 0 else None


def _doc_date(doc: dict) -> "datetime | None":
    """doc['date']/last_crawled_at 에서 날짜 1개를 datetime 으로. 못 찾으면 None."""
    for field in ("date", "last_crawled_at"):
        m = re.search(r"(\d{4})[-./](\d{1,2})[-./](\d{1,2})", str(doc.get(field) or ""))
        if m:
            try:
                return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                continue
    return None


def _freshness_boost(doc: dict, today: datetime) -> float:
    """date 기반 '일(day) 감쇠' 신선도 가중. RRF 스케일(±0.012)로 제한.

    구버전은 연도만 봐서 2026-01 과 2026-06 이 동일 가중 → 최신 변경공지를 못 올렸다.
    여기서는 며칠 전인지로 단계 가중: 최근일수록 ↑, 1년 초과는 소폭 감점.
    """
    dt = _doc_date(doc)
    if dt is None:
        return 0.0
    days = (today - dt).days
    if days < 0:
        return 0.0          # 미래로 오파싱된 값은 무시
    if days <= 7:
        return 0.012
    if days <= 30:
        return 0.008
    if days <= 90:
        return 0.004
    if days <= 365:
        return 0.0
    return -0.006           # 1년 초과 = 오래된 자료 소폭 감점


def _category_boost(doc: dict, target_cat: "str | None") -> float:
    """카테고리 의도 매칭. RRF 스케일로 축소(+0.008)."""
    if not target_cat:
        return 0.0
    return 0.008 if doc.get("data_category") == target_cat else 0.0


def _change_boost(doc: dict, is_change_q: bool) -> float:
    """'변동' 질의일 때만, 실제 변경공지로 보이는 문서를 끌어올림(+0.012)."""
    if not is_change_q:
        return 0.0
    text = (doc.get("title", "") or "") + " " + (doc.get("original_text") or doc.get("content") or "")
    return 0.012 if any(k in text for k in _CHANGE_DOC_KW) else 0.0


def apply_boost(docs: list[dict], question: str) -> list[dict]:
    """rrf_score 에 freshness + category + 변경키워드 보너스 더해서 재정렬.

    모든 보너스 합은 대략 ±0.03 이내로 묶여 RRF(최대 0.033) 관련도 신호를 압도하지 않는다.
    호환성: rrf_score 없는 결과(예: 단일 채널 검색)는 score 사용.
    """
    if not docs:
        return docs
    today = _today_dt()
    target_cat = _detect_category(question)
    is_change_q = bool(_CHANGE_Q_RE.search(question))
    for d in docs:
        base = float(d.get("rrf_score") or d.get("score") or 0.0)
        boost = (_freshness_boost(d, today)
                 + _category_boost(d, target_cat)
                 + _change_boost(d, is_change_q))
        d["meta_boost"] = boost
        d["final_score"] = base + boost
    return sorted(docs, key=lambda x: x.get("final_score", 0.0), reverse=True)
