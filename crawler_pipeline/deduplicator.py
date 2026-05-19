"""BGE-M3 임베딩 기반 의미 중복 제거. 유사도 0.95 이상이면 중복 처리."""
from typing import Any
import numpy as np


def dedup(docs: list[dict[str, Any]], threshold: float = 0.95) -> list[dict[str, Any]]:
    """코사인 유사도 기반 중복 제거. 임베딩 모델 없으면 원본 반환."""
    if len(docs) < 2:
        return docs

    texts = [d.get("original_text", "") for d in docs]

    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("BAAI/bge-m3")
        embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    except Exception as e:
        print(f"[deduplicator] 임베딩 실패: {e}, dedup 건너뜀")
        return docs

    keep = [True] * len(docs)
    for i in range(len(docs)):
        if not keep[i]:
            continue
        for j in range(i + 1, len(docs)):
            if not keep[j]:
                continue
            sim = float(np.dot(embeddings[i], embeddings[j]))
            if sim >= threshold:
                keep[j] = False

    result = [doc for doc, k in zip(docs, keep) if k]
    print(f"[deduplicator] {len(docs)} → {len(result)}건 (제거 {len(docs)-len(result)})")
    return result
