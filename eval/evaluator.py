# 평가셋 전체 실행 + LLM-as-judge + 결과 요약 출력

import json
import os
import time
from pathlib import Path
from typing import Dict, List, Optional

from eval.llm_judge import judge


def run_evaluation(
    testset_path: str = None,
    answers_path: str = None,
    output_path: str = None,
) -> Dict:
    """
    testset_path: 평가셋 JSONL (id, question, expected_answer)
    answers_path: 챗봇 답변 JSONL (id, answer) 또는 None (더미 사용)
    output_path: 결과 저장 경로
    """
    base = Path(__file__).parent.parent

    if testset_path is None:
        testset_path = str(base / "data" / "testset.jsonl")
    if output_path is None:
        output_path = str(base / "data" / "eval_results.json")

    testset = _load_jsonl(testset_path)
    if not testset:
        print(f"평가셋 없음: {testset_path}")
        return {}

    # 답변 로드 (없으면 더미)
    answers_map: Dict[str, str] = {}
    if answers_path:
        for item in _load_jsonl(answers_path):
            answers_map[item.get("id", "")] = item.get("answer", "")

    print(f"평가 시작: {len(testset)}개 질문")
    results = []
    scores_acc, scores_rel, scores_comp = [], [], []
    rejection_correct = 0
    rejection_total = 0

    for i, item in enumerate(testset):
        qid = item.get("id", f"eval_{i+1:04d}")
        question = item.get("question", "")
        expected = item.get("expected_answer", None)
        category_id = item.get("category_id", "")

        answer = answers_map.get(qid) or _dummy_answer(question, category_id)

        score = judge(question=question, answer=answer, expected=expected)

        entry = {
            "id": qid,
            "category_id": category_id,
            "question": question,
            "answer": answer,
            **score,
        }
        results.append(entry)
        scores_acc.append(score["accuracy"])
        scores_rel.append(score["relevance"])
        scores_comp.append(score["domain_compliance"])

        # 거절 정확도: 도메인 밖(Z) 질문에서 거절 답변 여부
        if category_id == "Z":
            rejection_total += 1
            if "해당 정보가 없습니다" in answer or "제공된 자료" in answer:
                rejection_correct += 1

        if (i + 1) % 20 == 0:
            print(f"  진행: {i+1}/{len(testset)}")

        # API 속도 제한
        if os.environ.get("JUDGE_MOCK", "0") != "1":
            time.sleep(0.3)

    n = len(results)
    avg_acc = sum(scores_acc) / n if n else 0
    avg_rel = sum(scores_rel) / n if n else 0
    avg_comp = sum(scores_comp) / n if n else 0
    rejection_accuracy = rejection_correct / rejection_total if rejection_total else 0

    summary = {
        "total_evaluated": n,
        "avg_accuracy": round(avg_acc, 3),
        "avg_relevance": round(avg_rel, 3),
        "avg_domain_compliance": round(avg_comp, 3),
        "avg_overall": round((avg_acc + avg_rel + avg_comp) / 3, 3),
        "rejection_accuracy": round(rejection_accuracy, 3),
        "details": results,
    }

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\n=== 평가 결과 ===")
    print(f"총 {n}개 평가")
    print(f"정확도 평균:      {avg_acc:.3f} / 5.0")
    print(f"관련성 평균:      {avg_rel:.3f} / 5.0")
    print(f"도메인 준수 평균: {avg_comp:.3f} / 5.0")
    print(f"종합 평균:        {(avg_acc+avg_rel+avg_comp)/3:.3f} / 5.0")
    print(f"거절 정확도:      {rejection_accuracy:.1%} ({rejection_correct}/{rejection_total})")
    print(f"결과 저장 → {output_path}")

    return summary


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


def _dummy_answer(question: str, category_id: str) -> str:
    """답변 파일 없을 때 사용하는 더미 답변"""
    if category_id == "Z":
        return "죄송합니다. 제공된 자료에 해당 정보가 없습니다. 충남대학교 관련 질문을 해주세요."
    return (
        f"충남대학교 관련 문의 감사합니다. "
        f"해당 내용은 학교 공식 홈페이지(www.cnu.ac.kr)를 참조해 주세요. "
        f"출처: www.cnu.ac.kr, 업데이트: 2026-05-19"
    )


if __name__ == "__main__":
    os.environ["JUDGE_MOCK"] = "1"
    run_evaluation()
