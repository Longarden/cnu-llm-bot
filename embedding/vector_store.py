"""Chroma persistent 벡터 DB. 메타데이터 6종 강제."""
import os
from typing import Any

CHROMA_PATH = os.path.join(os.path.dirname(__file__), "..", "chroma_db")
REQUIRED_METADATA = {"source_url", "data_category", "last_crawled_at", "valid_until", "freshness_tier", "original_text"}


_collection = None  # PersistentClient/컬렉션 핸들 싱글턴(질문마다 DB 새로 여는 비용 제거)


def _get_collection():
    global _collection
    if _collection is not None:
        return _collection
    import chromadb
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    _collection = client.get_or_create_collection("cnu_rag", metadata={"hnsw:space": "cosine"})
    return _collection


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
        embeddings = encode(batch_texts, show_progress_bar=True).tolist()
        collection.add(documents=batch_texts, embeddings=embeddings, metadatas=batch_meta, ids=batch_ids)
        print(f"[vector_store] {start + len(batch_texts)}/{len(texts)} 저장")

    print(f"[vector_store] 완료. 총 {count()}건")


def count() -> int:
    return _get_collection().count()


_index_checked = False


def ensure_index() -> bool:
    """인덱스가 비어 있으면 data/crawled 에서 재생성한다.

    chroma_db/ 는 용량 때문에 .gitignore 로 제외돼 있다. clone 직후에는 인덱스가 없는데,
    get_or_create_collection 은 빈 컬렉션을 조용히 만들어버려서 검색이 0건을 돌려주고도
    에러가 나지 않는다. 그러면 RAG 답변이 이유 없이 부실해진다 — 크래시보다 찾기 어렵다.
    그래서 첫 검색 전에 비어 있는지 확인하고, 비었으면 커밋된 크롤링 원본으로 다시 만든다.

    반환값: 재생성을 했으면 True, 이미 있으면 False.
    """
    global _index_checked
    if _index_checked:
        return False
    _index_checked = True
    if count() > 0:
        return False

    print("[vector_store] chroma_db 인덱스가 비어 있습니다 → data/crawled 로 재생성합니다.")
    print("[vector_store] bge-m3 임베딩이라 수 분 걸립니다. 한 번만 만들면 이후에는 재사용됩니다.")
    from embedding.chunker import chunk_documents
    from embedding.data_loader import load_scoped_docs

    docs = load_scoped_docs()
    chunks = chunk_documents(docs)
    print("[vector_store] 문서 %d건 → 청크 %d개" % (len(docs), len(chunks)))
    build_vector_db(chunks)
    return True


def get_all_docs(batch_size: int = 1000) -> list[dict]:
    """BM25 인덱스 구축용 전체 문서 반환."""
    ensure_index()
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
    ensure_index()
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
