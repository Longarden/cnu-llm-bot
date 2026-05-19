# 평가셋 200개 구성: 분포 강제 + 도메인 밖 하드코딩

import json
import random
from pathlib import Path
from typing import List, Dict

# 분포 정의 (합계 200)
DISTRIBUTION = {
    "A": 50,   # 시간성
    "B": 40,   # 학사
    "CD": 30,  # 행정+장학 합산
    "E": 25,   # 취업
    "F": 25,   # 학과
    "GH": 20,  # 생활+시설 합산
    "Z": 10,   # 도메인 밖
}

# 도메인 밖 질문 하드코딩 (10개)
DOMAIN_OUTSIDE_QUESTIONS: List[Dict] = [
    {"category_id": "Z", "category_name": "도메인밖", "subcategory": "날씨", "question": "오늘 대전 날씨 어때요?", "intent": "기상 정보 조회"},
    {"category_id": "Z", "category_name": "도메인밖", "subcategory": "정치", "question": "최근 대통령 지지율이 어떻게 되나요?", "intent": "정치 정보 조회"},
    {"category_id": "Z", "category_name": "도메인밖", "subcategory": "연예", "question": "BTS 새 앨범 언제 나와요?", "intent": "연예 정보 조회"},
    {"category_id": "Z", "category_name": "도메인밖", "subcategory": "스포츠", "question": "어제 야구 경기 결과 알려줘", "intent": "스포츠 결과 조회"},
    {"category_id": "Z", "category_name": "도메인밖", "subcategory": "타대학", "question": "연세대학교 수강신청은 어떻게 하나요?", "intent": "타 대학 정보 조회"},
    {"category_id": "Z", "category_name": "도메인밖", "subcategory": "일반상식", "question": "대한민국의 수도는 어디인가요?", "intent": "일반 상식"},
    {"category_id": "Z", "category_name": "도메인밖", "subcategory": "코로나", "question": "코로나 백신 예약 어떻게 해요?", "intent": "의료 정보 조회"},
    {"category_id": "Z", "category_name": "도메인밖", "subcategory": "영화", "question": "요즘 인기 영화 뭐야?", "intent": "영화 추천"},
    {"category_id": "Z", "category_name": "도메인밖", "subcategory": "요리", "question": "김치찌개 레시피 알려줘", "intent": "요리 정보"},
    {"category_id": "Z", "category_name": "도메인밖", "subcategory": "금융", "question": "삼성전자 주가가 얼마예요?", "intent": "주식 정보 조회"},
]


def build_testset(
    question_pool_path: str = None,
    output_path: str = None,
    n: int = 200,
) -> List[Dict]:
    """질문 풀에서 분포에 맞게 200개 평가셋 추출"""
    base = Path(__file__).parent.parent

    if question_pool_path is None:
        question_pool_path = str(base / "data" / "questions" / "question_pool.jsonl")
    if output_path is None:
        output_path = str(base / "data" / "testset.jsonl")

    pool = _load_jsonl(question_pool_path)
    if not pool:
        print(f"질문 풀 없음: {question_pool_path} → 더미 평가셋 생성")
        pool = _generate_dummy_pool()

    # 카테고리별 버킷 구성
    buckets: Dict[str, List[Dict]] = {}
    for item in pool:
        cid = item.get("category_id", "L")
        buckets.setdefault(cid, []).append(item)

    testset: List[Dict] = []
    idx = 0

    def _sample(category_ids: List[str], count: int) -> List[Dict]:
        candidates = []
        for cid in category_ids:
            candidates.extend(buckets.get(cid, []))
        random.shuffle(candidates)
        return candidates[:count]

    # 시간성 50
    testset.extend(_sample(["A"], DISTRIBUTION["A"]))
    # 학사 40
    testset.extend(_sample(["B"], DISTRIBUTION["B"]))
    # 행정+장학 30
    testset.extend(_sample(["C", "D"], DISTRIBUTION["CD"]))
    # 취업 25
    testset.extend(_sample(["E"], DISTRIBUTION["E"]))
    # 학과 25
    testset.extend(_sample(["F"], DISTRIBUTION["F"]))
    # 생활+시설 20
    testset.extend(_sample(["G", "H"], DISTRIBUTION["GH"]))
    # 도메인 밖 10 (하드코딩)
    testset.extend(DOMAIN_OUTSIDE_QUESTIONS[: DISTRIBUTION["Z"]])

    # 부족분 보충: 전체 풀에서 랜덤 보충
    if len(testset) < n:
        remaining = n - len(testset)
        all_non_z = [q for q in pool if q.get("category_id") != "Z"]
        random.shuffle(all_non_z)
        used_qs = {item["question"] for item in testset}
        for q in all_non_z:
            if q["question"] not in used_qs and remaining > 0:
                testset.append(q)
                remaining -= 1

    # ID 부여
    result = []
    for i, item in enumerate(testset[:n]):
        entry = {
            "id": f"eval_{i+1:04d}",
            "category_id": item.get("category_id", "L"),
            "category_name": item.get("category_name", ""),
            "subcategory": item.get("subcategory", ""),
            "question": item.get("question", ""),
            "expected_answer": item.get("expected_answer", None),
        }
        result.append(entry)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for entry in result:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print(f"평가셋 {len(result)}개 저장 → {output_path}")
    _print_distribution(result)
    return result


def _load_jsonl(path: str) -> List[Dict]:
    items = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    items.append(json.loads(line))
    except FileNotFoundError:
        pass
    return items


def _generate_dummy_pool() -> List[Dict]:
    """API 없이 빌드할 때 사용하는 최소 더미 풀"""
    from question_generation.question_pool_builder import CATEGORY_NODES, _fallback_questions
    pool = []
    for node in CATEGORY_NODES:
        for q in _fallback_questions(node, 30):
            pool.append({**node, **q})
    return pool


def _print_distribution(testset: List[Dict]) -> None:
    from collections import Counter
    counts = Counter(item["category_id"] for item in testset)
    print("\n평가셋 분포:")
    for cid, cnt in sorted(counts.items()):
        print(f"  {cid}: {cnt}개")


if __name__ == "__main__":
    build_testset()
