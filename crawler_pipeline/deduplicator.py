"""BGE-M3 임베딩 기반 의미 중복 제거. 유사도 0.95 이상이면 중복 처리.

중복쌍에서 '무엇을 남길지'는 최신성 우선: dedup 전에 게시일(date) 내림차순
(없으면 last_crawled_at)으로 정렬하므로, 아래 keep-first 로직이 자동으로
가장 최신 문서를 남기고 오래된 near-dup을 버린다. (날짜 무관 임의보존 → 최신우선)
"""
from typing import Any
import numpy as np


def _recency_key(d: dict[str, Any]) -> str:
    """최신성 정렬 키. ISO 문자열은 사전순=시간순이라 그대로 비교. date 우선, 없으면 크롤시각."""
    return (str(d.get("date") or "").strip() or str(d.get("last_crawled_at") or "").strip())


def dedup(docs: list[dict[str, Any]], threshold: float = 0.95) -> list[dict[str, Any]]:
    """코사인 유사도 기반 중복 제거(최신 보존). 임베딩 모델 없으면 원본 반환."""
    if len(docs) < 2:
        return docs

    # 최신순 정렬 → near-dup 쌍에서 최신(낮은 인덱스)이 살아남게 함.
    docs = sorted(docs, key=_recency_key, reverse=True)
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
