"""W4 CRAG escalation: 1차 검색이 ambiguous(<correct 임계)면 쿼리 변환을 켜고 한 번 더.

기존 거절(rejector)은 한 번의 검색만 보고 판정 → 검색 자체가 부실했어도 그대로 reject.
이 wrapper는 reranker 점수가 ambiguous일 때 query_transform/expanded BM25 +
HyDE dense로 한 번 더 시도하고, 둘 중 더 나은 결과를 채택.

사용: 콜랩에서 retrieve_with_escalation(question, n, llm_call=qwen_call)
"""
import os
from typing import Callable, Optional

LLMCall = Callable[[str], str]

# 환경변수로 임계 조정 가능. rejector와 동일한 기준 사용.
AMBIGUOUS_THRESHOLD = float(os.environ.get("REJECT_RERANK_CORRECT", "0.62"))


def retrieve_with_escalation(question: str, n_results: int = 10,
                             llm_call: Optional[LLMCall] = None,
                             date_filter: Optional[dict] = None,
                             use_meta_boost: bool = True) -> list[dict]:
    """1차 검색 → 리랭크 → ambiguous면 쿼리 변환 켜고 escalation → 더 좋은 쪽 채택."""
    from .hybrid_retriever import retrieve
    from .reranker import rerank

    # 1차: 기본 검색 (쿼리 변환 OFF, meta boost는 켜둠)
    base_results = retrieve(
        question, n_results=n_results,
        date_filter=date_filter,
        llm_call=None,
        use_query_transform=False,
        use_meta_boost=use_meta_boost,
    )
    base_ranked = rerank(question, base_results, top_k=n_results)
    base_top = base_ranked[0].get("rerank_score", 0.0) if base_ranked else 0.0

    # ambiguous 또는 incorrect 가 아니면 끝
    if base_top >= AMBIGUOUS_THRESHOLD or llm_call is None:
        return base_ranked

    # 2차: 쿼리 변환 켜고 다시 (더 넓게 가져옴)
    try:
        esc_results = retrieve(
            question, n_results=n_results * 2,
            date_filter=date_filter,
            llm_call=llm_call,
            use_query_transform=True,
            use_meta_boost=use_meta_boost,
        )
    except Exception as e:
        print(f"[crag_escalation] 2차 검색 실패, 1차 결과 사용: {e}")
        return base_ranked

    esc_ranked = rerank(question, esc_results, top_k=n_results)
    esc_top = esc_ranked[0].get("rerank_score", 0.0) if esc_ranked else 0.0

    # 두 결과 중 top score 높은 쪽 채택. 동률이면 1차(deterministic).
    if esc_top > base_top + 0.02:  # 0.02 마진 — 우연한 차이는 무시
        for d in esc_ranked:
            d["escalated"] = True
        return esc_ranked
    return base_ranked
