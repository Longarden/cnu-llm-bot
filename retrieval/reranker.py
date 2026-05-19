"""BGE-reranker-v2-m3 최종 재정렬. RERANK=1 env 게이트."""
import os
from typing import Any


def rerank(question: str, docs: list[dict[str, Any]], top_k: int = 3) -> list[dict[str, Any]]:
    """RERANK=1이면 BGE-reranker 사용. 아니면 rrf_score 기준 top_k 반환."""
    if os.getenv("RERANK", "0") != "1":
        return docs[:top_k]

    try:
        from FlagEmbedding import FlagReranker
        reranker = FlagReranker("BAAI/bge-reranker-v2-m3", use_fp16=True)
        pairs = [(question, d.get("text", d.get("original_text", ""))) for d in docs]
        scores = reranker.compute_score(pairs)
        for doc, score in zip(docs, scores):
            doc["rerank_score"] = float(score)
        return sorted(docs, key=lambda x: x.get("rerank_score", 0), reverse=True)[:top_k]
    except Exception as e:
        print(f"[reranker] 실패: {e}, rrf_score 기준 사용")
        return docs[:top_k]
