"""BM25 + BGE-M3 Dense + Reciprocal Rank Fusion (k=60) 하이브리드 검색."""
from typing import Any
import os

_bm25 = None
_bm25_docs: list[dict] = []


def _rrf_score(rank: int, k: int = 60) -> float:
    return 1.0 / (k + rank)


def _reciprocal_rank_fusion(sparse_results: list[dict], dense_results: list[dict]) -> list[dict]:
    """두 랭킹 리스트를 RRF로 융합."""
    scores: dict[str, float] = {}
    doc_map: dict[str, dict] = {}

    def _key(item: dict) -> str:
        return item.get("text") or item.get("original_text", "")

    for rank, item in enumerate(sparse_results):
        key = _key(item)
        scores[key] = scores.get(key, 0.0) + _rrf_score(rank)
        item["sparse_score"] = item.get("score", 0.0)
        item["rrf_score"] = scores[key]
        doc_map[key] = item

    for rank, item in enumerate(dense_results):
        key = _key(item)
        scores[key] = scores.get(key, 0.0) + _rrf_score(rank)
        existing = doc_map.get(key, item)
        existing["dense_score"] = item.get("score", 0.0)
        existing["rrf_score"] = scores[key]
        doc_map[key] = existing

    for key, item in doc_map.items():
        item.setdefault("sparse_score", 0.0)
        item.setdefault("dense_score", 0.0)
        item["rrf_score"] = scores[key]

    return sorted(doc_map.values(), key=lambda x: x["rrf_score"], reverse=True)


def build_bm25_index(docs: list[dict[str, Any]]) -> None:
    """BM25 인덱스 구축. 전체 청크 로드 후 호출."""
    global _bm25, _bm25_docs
    from rank_bm25 import BM25Okapi
    _bm25_docs = docs
    tokenized = [d.get("original_text", "").split() for d in docs]
    _bm25 = BM25Okapi(tokenized)


def init_bm25_from_db() -> None:
    """Chroma DB에서 전체 문서를 로드해 BM25 인덱스 자동 구축."""
    from embedding.vector_store import get_all_docs
    docs = get_all_docs()
    if docs:
        build_bm25_index(docs)
        print(f"[hybrid_retriever] BM25 인덱스 구축 완료: {len(docs)}건")


def retrieve(question: str, n_results: int = 10, date_filter: dict | None = None) -> list[dict]:
    """하이브리드 검색. sparse + dense + RRF 융합 결과 반환."""
    sparse_results = _sparse_search(question, n_results)
    dense_results = _dense_search(question, n_results, date_filter)
    fused = _reciprocal_rank_fusion(sparse_results, dense_results)
    return fused[:n_results]


def _sparse_search(question: str, n: int) -> list[dict]:
    if _bm25 is None or not _bm25_docs:
        return []
    scores = _bm25.get_scores(question.split())
    top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:n]
    results = []
    for idx in top_indices:
        doc = dict(_bm25_docs[idx])
        doc["score"] = float(scores[idx])
        results.append(doc)
    return results


def _dense_search(question: str, n: int, where: dict | None = None) -> list[dict]:
    try:
        from embedding.vector_store import query
        return query(question, n_results=n, where=where)
    except Exception as e:
        print(f"[hybrid_retriever] dense 검색 실패: {e}")
        return []
