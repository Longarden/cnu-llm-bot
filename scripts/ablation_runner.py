"""5조합 ablation runner — 콜랩에서 import 해 호출.

조합:
  baseline   : 옵션 다 OFF (현재 RAG)
  +meta      : W3 metadata_boost ON
  +query     : W2 query_transform ON
  +crag_esc  : W4 CRAG escalation + W3 ON
  full       : W2+W3+W4+W5(self_verify) 다 ON

콜랩 사용 예:
    from scripts.ablation_runner import run_ablation, score_ablation
    from interface.answer_questions import _rag_answer
    def llm_generate(q, docs):
        # LLM 호출 wrapper. 콜랩에서 Qwen으로 구현.
        ...
    questions = [json.loads(l) for l in open('data/testset.jsonl', encoding='utf-8')]
    results = run_ablation(questions, llm_call=qwen_call, llm_generate=llm_generate,
                            out_path='data/ablation_answers.json', n_results=5)
    from eval.llm_judge import judge
    scores = score_ablation(results, judge)
    print_scoreboard(scores)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Optional

LLMCall = Callable[[str], str]
LLMGenerate = Callable[[str, list[dict]], str]  # (question, retrieved_docs) -> answer

CONFIGS = {
    "baseline":   dict(use_query_transform=False, use_meta_boost=False, use_crag_esc=False, use_self_verify=False),
    "+meta":      dict(use_query_transform=False, use_meta_boost=True,  use_crag_esc=False, use_self_verify=False),
    "+query":     dict(use_query_transform=True,  use_meta_boost=False, use_crag_esc=False, use_self_verify=False),
    "+crag_esc":  dict(use_query_transform=False, use_meta_boost=True,  use_crag_esc=True,  use_self_verify=False),
    "full":       dict(use_query_transform=True,  use_meta_boost=True,  use_crag_esc=True,  use_self_verify=True),
}


def _retrieve_with_config(question: str, cfg: dict, llm_call: Optional[LLMCall],
                          n_results: int = 5, date_filter: Optional[dict] = None) -> list[dict]:
    from retrieval.hybrid_retriever import retrieve
    if cfg["use_crag_esc"]:
        from retrieval.crag_escalation import retrieve_with_escalation
        return retrieve_with_escalation(
            question, n_results=n_results,
            llm_call=llm_call if cfg["use_query_transform"] else None,
            date_filter=date_filter,
            use_meta_boost=cfg["use_meta_boost"],
        )
    return retrieve(
        question, n_results=n_results,
        date_filter=date_filter,
        llm_call=llm_call if cfg["use_query_transform"] else None,
        use_query_transform=cfg["use_query_transform"],
        use_meta_boost=cfg["use_meta_boost"],
    )


def answer_with_config(question: str, cfg: dict, llm_call: Optional[LLMCall],
                       llm_generate: LLMGenerate, n_results: int = 5,
                       date_filter: Optional[dict] = None) -> tuple[str, list[dict]]:
    """한 질문 × 한 조합 → 답변. self_verify ON 이면 grounded=False시 거절 문구."""
    docs = _retrieve_with_config(question, cfg, llm_call, n_results, date_filter)
    answer = llm_generate(question, docs) if docs else "제공된 자료에 해당 정보가 없습니다."
    if cfg["use_self_verify"] and docs and llm_call:
        from generation.self_verify import verify_answer
        v = verify_answer(question, answer, docs, llm_call)
        if not v.get("grounded", True):
            answer = f"제공된 자료에 해당 정보가 없습니다. (self_verify 거절: {v.get('reason','')[:60]})"
    return answer, docs


def run_ablation(questions: list[dict],
                 llm_call: LLMCall, llm_generate: LLMGenerate,
                 out_path: str = "data/ablation_answers.json",
                 n_results: int = 5,
                 configs: dict | None = None,
                 verbose_every: int = 25) -> dict:
    """전체 ablation 실행 + checkpoint 저장. 반환: {cfg_name: [{id,question,answer,...}]}"""
    cfgs = configs or CONFIGS
    out_path = str(out_path)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)

    # resume: 기존 파일 있으면 이어함
    results: dict = {}
    if Path(out_path).exists():
        try:
            results = json.load(open(out_path, encoding="utf-8"))
        except Exception:
            results = {}

    for cfg_name, cfg in cfgs.items():
        already = results.get(cfg_name, [])
        if len(already) >= len(questions):
            print(f"[{cfg_name}] 이미 완료 ({len(already)}건) 스킵")
            continue
        start = len(already)
        print(f"=== {cfg_name} (start {start}/{len(questions)}) ===")
        out = list(already)
        for i in range(start, len(questions)):
            q = questions[i]
            qtext = q.get("question", "") or q.get("query", "")
            qid = q.get("id", f"q{i}")
            try:
                ans, docs = answer_with_config(qtext, cfg, llm_call, llm_generate, n_results)
            except Exception as e:
                ans, docs = f"[error] {e}", []
            out.append({"id": qid, "question": qtext, "answer": ans, "config": cfg_name})
            if (i + 1) % verbose_every == 0:
                print(f"  {i+1}/{len(questions)}")
                results[cfg_name] = out
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(results, f, ensure_ascii=False, indent=2)
        results[cfg_name] = out
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"  {cfg_name} 완료. 저장: {out_path}")
    return results


def score_ablation(results: dict, score_func: Callable, expected_map: dict | None = None) -> dict:
    """answers × judge → 평균 점수 행렬.

    score_func 시그니처: score_func(question, answer, expected=None) -> dict (accuracy/relevance/...)
    """
    out: dict = {}
    for cfg_name, answers in results.items():
        scores: list[dict] = []
        for a in answers:
            exp = (expected_map or {}).get(a.get("id"), None)
            try:
                s = score_func(a["question"], a["answer"], exp)
            except TypeError:
                s = score_func(a["question"], a["answer"])
            scores.append(s)
        if not scores:
            out[cfg_name] = {}
            continue
        keys = [k for k, v in scores[0].items() if isinstance(v, (int, float))]
        avg = {k: round(sum(s.get(k, 0) for s in scores) / len(scores), 3) for k in keys}
        out[cfg_name] = avg
    return out


def print_scoreboard(scores: dict) -> None:
    """ablation 점수 표로 출력."""
    if not scores:
        print("점수 없음")
        return
    first = next(iter(scores.values()))
    cols = list(first.keys())
    header = f"  {'config':<14} | " + " | ".join(f"{c:>10}" for c in cols)
    print(header)
    print("  " + "-" * (len(header) - 2))
    for cfg_name, s in scores.items():
        row = f"  {cfg_name:<14} | " + " | ".join(f"{s.get(c, 0):>10.3f}" for c in cols)
        print(row)
