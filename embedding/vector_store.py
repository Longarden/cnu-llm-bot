"""Chroma persistent 벡터 DB. 메타데이터 6종 강제."""
import os
from typing import Any

CHROMA_PATH = os.path.join(os.path.dirname(__file__), "..", "chroma_db")
REQUIRED_METADATA = {"source_url", "data_category", "last_crawled_at", "valid_until", "freshness_tier", "original_text"}


def _get_collection():
    import chromadb
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    return client.get_or_create_collection("cnu_rag", metadata={"hnsw:space": "cosine"})


def build_vector_db(docs: list[dict[str, Any]], batch_size: int = 100) -> None:
    """청크 목록을 Chroma에 저장. 메타데이터 6종 없으면 빈 문자열로 채움."""
    from embedding.embedder import encode

    collection = _get_collection()
    texts, metadatas, ids = [], [], []

    for i, doc in enumerate(docs):
        text = doc.get("original_text", "")
        if not text:
            continue
        meta = {k: str(doc.get(k, "")) for k in REQUIRED_METADATA}
        texts.append(text)
        metadatas.append(meta)
        ids.append(f"doc_{i}")

    for start in range(0, len(texts), batch_size):
        batch_texts = texts[start:start + batch_size]
        batch_meta = metadatas[start:start + batch_size]
        batch_ids = ids[start:start + batch_size]
        embeddings = encode(batch_texts).tolist()
        collection.add(documents=batch_texts, embeddings=embeddings, metadatas=batch_meta, ids=batch_ids)
        print(f"[vector_store] {start + len(batch_texts)}/{len(texts)} 저장")

    print(f"[vector_store] 완료. 총 {count()}건")


def count() -> int:
    return _get_collection().count()


def get_all_docs(batch_size: int = 1000) -> list[dict]:
    """BM25 인덱스 구축용 전체 문서 반환."""
    collection = _get_collection()
    total = collection.count()
    if total == 0:
        return []
    results = []
    for offset in range(0, total, batch_size):
        res = collection.get(
            limit=batch_size,
            offset=offset,
            include=["documents", "metadatas"],
        )
        for doc, meta in zip(res["documents"], res["metadatas"]):
            entry = dict(meta)
            entry["original_text"] = doc
            results.append(entry)
    return results


def query(text: str, n_results: int = 10, where: dict | None = None) -> list[dict]:
    from embedding.embedder import encode
    collection = _get_collection()
    embedding = encode([text])[0].tolist()
    kwargs: dict = {"query_embeddings": [embedding], "n_results": n_results, "include": ["documents", "metadatas", "distances"]}
    if where:
        kwargs["where"] = where
    res = collection.query(**kwargs)
    results = []
    for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
        results.append({"text": doc, "metadata": meta, "score": 1 - dist})
    return results
