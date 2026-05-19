"""RecursiveCharacterTextSplitter 기반 청킹 (400자 / 50자 오버랩)."""
from typing import Any


def chunk_documents(docs: list[dict[str, Any]], chunk_size: int = 400, overlap: int = 50) -> list[dict[str, Any]]:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = []
    for doc in docs:
        text = doc.get("original_text", "")
        if not text:
            continue
        for i, chunk_text in enumerate(splitter.split_text(text)):
            chunk = dict(doc)
            chunk["original_text"] = chunk_text
            chunk["chunk_index"] = i
            chunks.append(chunk)
    return chunks
