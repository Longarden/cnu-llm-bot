"""BGE-reranker-v2-m3 최종 재정렬. RERANK=1 env 게이트.

리랭커는 sentence-transformers CrossEncoder로 로드한다.
(FlagEmbedding FlagReranker는 transformers 버전 비호환 -
 'XLMRobertaTokenizer has no attribute prepare_for_model' 발생.)
"""
import os
from typing import Any

_cross_encoder = None  # 모델 1회 로드 후 캐시 (호출마다 재로드 방지)


def _get_cross_encoder():
    """CrossEncoder 지연 로드 + 캐시. 로드 실패 시 False 표시."""
    global _cross_encoder
    if _cross_encoder is None:
        try:
            from sentence_transformers import CrossEncoder
            _cross_encoder = CrossEncoder("BAAI/bge-reranker-v2-m3", max_length=512)
        except Exception as e:
            print(f"[reranker] CrossEncoder 로드 실패: {e}, 폴백")
            _cross_encoder = False
    return _cross_encoder


def rerank(question: str, docs: list[dict[str, Any]], top_k: int = 3) -> list[dict[str, Any]]:
    """RERANK=1이면 CrossEncoder 사용. 아니면 융합 순위(rrf) 기준 top_k 반환."""
    if os.getenv("RERANK", "0") != "1" or not docs:
        return docs[:top_k]

    model = _get_cross_encoder()
    if not model:
        return docs[:top_k]

    try:
        import math
        pairs = [[question, d.get("text", d.get("original_text", "")) or ""] for d in docs]
        scores = model.predict(pairs)
        for doc, score in zip(docs, scores):
            raw = float(score)
            doc["rerank_raw"] = raw
            # bge-reranker는 로짓 출력 -> 시그모이드로 0~1 정규화(공식 normalize 방식).
            # CRAG 밴드 판정(Correct/Ambiguous/Incorrect)이 0~1에서 의미를 가짐.
            doc["rerank_score"] = 1.0 / (1.0 + math.exp(-raw))
        return sorted(docs, key=lambda x: x.get("rerank_score", 0.0), reverse=True)[:top_k]
    except Exception as e:
        print(f"[reranker] 재정렬 실패: {e}, 융합 순위 사용")
        return docs[:top_k]
