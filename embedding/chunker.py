"""문서 청킹 (400자 / 50자 오버랩). 외부 의존성 없는 자체 구현.

langchain RecursiveCharacterTextSplitter와 동등한 동작:
경계를 자연스러운 구분자(문단/줄/문장/공백)에서 끊고, 청크 간 overlap을 둠.
콜랩 재현성을 위해 외부 패키지(langchain_text_splitters)를 쓰지 않는다.
우리 문서 대부분(<400자)은 한 청크로 그대로 통과, 긴 문서만 분할됨.
"""
from typing import Any


def _split_window(text: str, size: int, overlap: int) -> list[str]:
    """길이 size 윈도우로 자르되, 경계를 구분자에서 끊고 overlap 적용."""
    chunks: list[str] = []
    start, n = 0, len(text)
    while start < n:
        end = min(start + size, n)
        if end < n:
            # end 근처에서 자연스러운 구분자(문단>줄>문장>공백)로 뒤로 당겨 끊기
            window = text[start:end]
            cut = max(window.rfind("\n\n"), window.rfind("\n"),
                      window.rfind(". "), window.rfind(" "))
            if cut > size * 0.5:  # 너무 짧게 잘리는 것 방지
                end = start + cut + 1
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= n:
            break
        start = max(end - overlap, 0)
    return chunks


def chunk_documents(docs: list[dict[str, Any]], chunk_size: int = 400, overlap: int = 50) -> list[dict[str, Any]]:
    """각 문서의 original_text를 청크로 분할. 메타데이터는 복사하고 chunk_index 부여."""
    chunks: list[dict[str, Any]] = []
    for doc in docs:
        text = (doc.get("original_text", "") or "").strip()
        if not text:
            continue
        pieces = [text] if len(text) <= chunk_size else _split_window(text, chunk_size, overlap)
        for i, piece in enumerate(pieces):
            chunk = dict(doc)
            chunk["original_text"] = piece
            chunk["chunk_index"] = i
            chunks.append(chunk)
    return chunks
