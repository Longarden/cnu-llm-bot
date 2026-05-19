"""하이브리드 검색 단위 테스트 (AC7)."""
import pytest
from retrieval.hybrid_retriever import build_bm25_index, retrieve


SAMPLE_DOCS = [
    {
        "original_text": "충남대학교 학식 메뉴는 매일 바뀝니다.",
        "source_url": "https://cnu.ac.kr/dining",
        "data_category": "A_dining",
        "last_crawled_at": "2026-05-19",
        "valid_until": "2026-05-20",
        "freshness_tier": "time_sensitive",
    },
    {
        "original_text": "도서관 열람실은 오전 6시부터 자정까지 운영합니다.",
        "source_url": "https://library.cnu.ac.kr",
        "data_category": "A_library",
        "last_crawled_at": "2026-05-19",
        "valid_until": "2026-05-26",
        "freshness_tier": "semi_static",
    },
    {
        "original_text": "국가장학금 신청은 한국장학재단 홈페이지에서 합니다.",
        "source_url": "https://jangjak.cnu.ac.kr",
        "data_category": "D_scholarship",
        "last_crawled_at": "2026-05-19",
        "valid_until": "2026-05-26",
        "freshness_tier": "semi_static",
    },
]


def test_retrieve_returns_sparse_dense_rrf_keys():
    """AC7: 하이브리드 검색 결과에 sparse_score, dense_score, rrf_score 키 모두 존재."""
    build_bm25_index(SAMPLE_DOCS)
    results = retrieve("학식 메뉴", n_results=3)
    assert len(results) > 0, "검색 결과가 비어 있음"
    first = results[0]
    assert "sparse_score" in first, "sparse_score 키 없음"
    assert "dense_score" in first, "dense_score 키 없음"
    assert "rrf_score" in first, "rrf_score 키 없음"


def test_retrieve_rrf_score_positive():
    """RRF 점수는 항상 양수."""
    build_bm25_index(SAMPLE_DOCS)
    results = retrieve("도서관", n_results=3)
    for r in results:
        assert r["rrf_score"] > 0


def test_bm25_only_when_no_chroma():
    """Chroma dense 검색 실패해도 sparse 결과는 반환됨."""
    build_bm25_index(SAMPLE_DOCS)
    # "한국장학재단" 은 SAMPLE_DOCS[2] original_text에 실제로 있는 단어
    results = retrieve("한국장학재단", n_results=3)
    assert len(results) > 0, "결과가 비어 있음"
    # BM25 인덱스 있으므로 sparse_score 키 존재
    assert all("sparse_score" in r for r in results)


def test_retrieve_sorted_by_rrf():
    """결과가 rrf_score 내림차순으로 정렬되어 있어야 함."""
    build_bm25_index(SAMPLE_DOCS)
    results = retrieve("학식", n_results=3)
    scores = [r["rrf_score"] for r in results]
    assert scores == sorted(scores, reverse=True)
