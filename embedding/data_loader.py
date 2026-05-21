"""크롤 데이터 로더 (스코프 적용).

Ver2 스코프: 학과 = 컴퓨터인공지능학부(department_general)만.
다른 학과 파일(departments_humanities_social.json 등)은 제외.
PDF/HWP는 이번 빌드 제외 (HTML 텍스트만).

우선순위:
1. data/crawled/all_dedup.json 이 있으면 그걸 사용 (이미 14 카테고리 통합 + 중복제거,
   컴공 department_general 포함, 다른 학과 미포함 -> 스코프 일치).
2. 없으면 개별 카테고리 JSON을 로드하되 학과 denylist 파일 제외.
"""
import json
import os
from typing import Any

CRAWLED_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "crawled")

# 스코프 제외 파일 (컴공 외 학과 풀크롤 결과). 로드하지 않음.
DEPARTMENT_DENYLIST = {
    "departments_humanities_social.json",
    "departments_natural_eng_pharm_med.json",
    "departments_others.json",
    "all_departments.json",
}

# 개별 카테고리 로드 시 사용할 화이트리스트 (14 카테고리 + 컴공 department_general).
CATEGORY_FILES = [
    "academic.json", "administration.json", "scholarship.json", "career.json",
    "dining.json", "library.json", "shuttle.json", "dormitory.json",
    "department_general.json",  # 컴퓨터인공지능학부
    "facilities.json", "general.json",
    "extracurricular.json", "international.json", "student_life.json",
    "notices.json",
]


def load_scoped_docs(prefer_dedup: bool = True) -> list[dict[str, Any]]:
    """스코프 적용된 문서 목록 반환.

    prefer_dedup=True 면 all_dedup.json 우선 사용.
    """
    dedup_path = os.path.join(CRAWLED_DIR, "all_dedup.json")
    if prefer_dedup and os.path.exists(dedup_path):
        with open(dedup_path, encoding="utf-8") as f:
            docs = json.load(f)
        print(f"[data_loader] all_dedup.json 로드: {len(docs)}건 (스코프 통합본)")
        return docs

    # 폴백: 개별 카테고리 파일 로드 (denylist 제외)
    docs: list[dict] = []
    for fname in CATEGORY_FILES:
        path = os.path.join(CRAWLED_DIR, fname)
        if fname in DEPARTMENT_DENYLIST:
            continue
        if not os.path.exists(path):
            print(f"[data_loader] 스킵(없음): {fname}")
            continue
        with open(path, encoding="utf-8") as f:
            cat_docs = json.load(f)
        docs.extend(cat_docs)
        print(f"[data_loader] {fname}: {len(cat_docs)}건")
    print(f"[data_loader] 개별 로드 합계: {len(docs)}건")
    return docs


def scope_summary() -> dict:
    """로드된 데이터의 카테고리별 분포 요약 (검증용)."""
    docs = load_scoped_docs()
    cats: dict[str, int] = {}
    for d in docs:
        c = d.get("data_category", "?")
        cats[c] = cats.get(c, 0) + 1
    return {"total": len(docs), "categories": cats}


if __name__ == "__main__":
    summary = scope_summary()
    print(f"총 {summary['total']}건")
    for cat, n in sorted(summary["categories"].items()):
        print(f"  {cat}: {n}")
