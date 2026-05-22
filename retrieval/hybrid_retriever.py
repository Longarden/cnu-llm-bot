"""BM25 + BGE-M3 Dense + Reciprocal Rank Fusion (k=60) 하이브리드 검색."""
from typing import Any
import os

_bm25 = None
_bm25_docs: list[dict] = []
_kiwi = None


def _tokenize(text: str) -> list[str]:
    """한국어 형태소 토크나이저 (kiwipiepy). 없으면 공백분할 폴백.

    '졸업학점' 같은 붙임말을 형태소로 분리해 질문 '졸업 학점'과 매칭되게 함.
    """
    global _kiwi
    if _kiwi is None:
        try:
            from kiwipiepy import Kiwi
            _kiwi = Kiwi()
        except Exception:
            _kiwi = False  # 폴백 표시
    if _kiwi is False:
        return text.split()
    try:
        return [t.form for t in _kiwi.tokenize(text)]
    except Exception:
        return text.split()


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
    tokenized = [_tokenize(d.get("original_text", "")) for d in docs]
    _bm25 = BM25Okapi(tokenized)


def init_bm25_from_db() -> None:
    """Chroma DB에서 전체 문서를 로드해 BM25 인덱스 자동 구축."""
    from embedding.vector_store import get_all_docs
    docs = get_all_docs()
    if docs:
        build_bm25_index(docs)
        print(f"[hybrid_retriever] BM25 인덱스 구축 완료: {len(docs)}건")


def retrieve(question: str, n_results: int = 10, date_filter: dict | None = None) -> list[dict]:
    """하이브리드 검색. sparse + dense + RRF 융합 결과 반환.

    date_filter는 Chroma where로 넘기지 않고(문자열 valid_until 타입 크래시 회피)
    융합 결과를 후처리로 거른다. ISO 날짜(YYYY-MM-DD)는 사전식 비교=시간순.
    """
    # 날짜 필터가 있으면 후처리에서 일부가 빠질 수 있어 넉넉히 검색
    pull = n_results * 2 if date_filter else n_results
    sparse_results = _sparse_search(question, pull)
    dense_results = _dense_search(question, pull)
    fused = _reciprocal_rank_fusion(sparse_results, dense_results)
    if date_filter:
        fused = _apply_date_filter(fused, date_filter)
    fused = _apply_hall_filter(fused, question)
    return fused[:n_results]


def _apply_hall_filter(docs: list[dict], question: str) -> list[dict]:
    """질문이 특정 학생회관(제N학생회관)을 지목하면 다른 관 메뉴 청크를 제거.

    검색은 1등으로 맞는 관을 줘도 비슷한 다른 관 청크가 같이 딸려와
    LLM이 답 쓸 때 섞는 것을 방지(컨텍스트에서 경쟁 관 제거).
    질문에 학생회관 지목이 없으면 그대로 통과.
    """
    import re
    m = re.search(r"제?\s*([1-4])\s*학(?:생회관|관)", question)
    if not m:
        return docs
    n = m.group(1)
    target = f"제{n}학생회관"
    others = [f"제{k}학생회관" for k in "1234" if k != n]
    out = []
    for d in docs:
        txt = (d.get("original_text", "") or d.get("text", ""))
        # 다른 관을 언급하는데 지목한 관은 없으면 = 경쟁 관 메뉴 -> 제외
        if any(o in txt for o in others) and target not in txt:
            continue
        out.append(d)
    return out


def _apply_date_filter(docs: list[dict], date_filter: dict) -> list[dict]:
    """valid_until 후처리 필터. {'valid_until': {'$gte': 'YYYY-MM-DD'}} 형태 지원.

    valid_until 이 없는 문서(상시 유효 정보: 학과 위치 등)는 통과시킨다.
    """
    spec = date_filter.get("valid_until", {}) if isinstance(date_filter, dict) else {}
    min_date = spec.get("$gte") if isinstance(spec, dict) else None
    if not min_date:
        return docs
    min_date = str(min_date)[:10]
    out = []
    for d in docs:
        vu = str(d.get("valid_until", "") or "").strip()[:10]
        if not vu or vu >= min_date:  # 만료일 없으면 상시 유효로 간주
            out.append(d)
    return out


def _sparse_search(question: str, n: int) -> list[dict]:
    if _bm25 is None or not _bm25_docs:
        return []
    scores = _bm25.get_scores(_tokenize(question))
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
        raw = query(question, n_results=n, where=where)
        # sparse 결과와 형태 통일: original_text + 메타데이터 평탄화 (RRF 키 일치, 카테고리 보존)
        flat = []
        for r in raw:
            meta = r.get("metadata", {}) or {}
            item = dict(meta)
            item["original_text"] = r.get("text", "") or meta.get("original_text", "")
            item["score"] = r.get("score", 0.0)
            flat.append(item)
        return flat
    except Exception as e:
        print(f"[hybrid_retriever] dense 검색 실패: {e}")
        return []
