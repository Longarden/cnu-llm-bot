"""벡터 DB 메타데이터 6종 강제 검증 테스트 (AC5)."""
import pytest
from unittest.mock import MagicMock, patch
from embedding.vector_store import REQUIRED_METADATA


def test_required_metadata_keys():
    """AC5: 6종 메타데이터 키가 정의되어 있어야 함."""
    assert "source_url" in REQUIRED_METADATA
    assert "data_category" in REQUIRED_METADATA
    assert "last_crawled_at" in REQUIRED_METADATA
    assert "valid_until" in REQUIRED_METADATA
    assert "freshness_tier" in REQUIRED_METADATA
    assert "original_text" in REQUIRED_METADATA
    assert len(REQUIRED_METADATA) == 6


def test_build_vector_db_fills_missing_metadata():
    """메타데이터 일부 누락 시 빈 문자열로 채워서 저장."""
    doc_missing_meta = {
        "original_text": "테스트 문서입니다.",
        "source_url": "https://cnu.ac.kr/test",
        # data_category, last_crawled_at, valid_until, freshness_tier 누락
    }

    captured_metadatas = []

    mock_collection = MagicMock()
    def fake_add(documents, embeddings, metadatas, ids):
        captured_metadatas.extend(metadatas)

    mock_collection.add.side_effect = fake_add
    mock_collection.count.return_value = 1

    import numpy as np
    mock_encode = MagicMock(return_value=np.array([[0.1] * 1024]))

    with patch("embedding.vector_store._get_collection", return_value=mock_collection), \
         patch("embedding.embedder.encode", mock_encode):
        from embedding.vector_store import build_vector_db
        build_vector_db([doc_missing_meta])

    assert len(captured_metadatas) == 1
    meta = captured_metadatas[0]
    for key in REQUIRED_METADATA:
        assert key in meta, f"메타데이터 키 '{key}' 없음"
        assert isinstance(meta[key], str), f"메타데이터 '{key}'가 문자열이 아님"


def test_build_vector_db_skips_empty_text():
    """original_text가 없는 문서는 건너뜀."""
    docs = [
        {"original_text": "", "source_url": "https://cnu.ac.kr/a"},
        {"source_url": "https://cnu.ac.kr/b"},
    ]
    mock_collection = MagicMock()
    mock_collection.count.return_value = 0

    with patch("embedding.vector_store._get_collection", return_value=mock_collection), \
         patch("embedding.embedder.encode", return_value=[]):
        from embedding.vector_store import build_vector_db
        build_vector_db(docs)

    mock_collection.add.assert_not_called()
