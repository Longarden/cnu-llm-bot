"""청킹 적용해서 벡터DB 재빌드. (청킹 ON 결정 반영)
load_scoped_docs -> chunk_documents -> 컬렉션 리셋 -> build_vector_db.
BM25는 검색 시 DB에서 자동 구축되므로 여기선 벡터DB만.
실행: python scripts/rebuild_index.py   (miniconda python)"""
import sys, io, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from embedding.data_loader import load_scoped_docs
from embedding.chunker import chunk_documents
from embedding.vector_store import build_vector_db, count, CHROMA_PATH

print("=== 1. 데이터 로드 ===")
docs = load_scoped_docs()
print(f"문서 {len(docs)}건")

print("=== 2. 청킹 (400/50) ===")
chunks = chunk_documents(docs)
print(f"청크 {len(chunks)}개")

print("=== 3. 기존 컬렉션 리셋 ===")
import chromadb
client = chromadb.PersistentClient(path=CHROMA_PATH)
try:
    client.delete_collection("cnu_rag")
    print("기존 컬렉션 삭제")
except Exception as e:
    print(f"삭제 스킵: {e}")

print("=== 4. 벡터DB 빌드 (bge-m3, 청크 단위) ===")
build_vector_db(chunks)
print(f"벡터DB 청크 수: {count()}")
print("\n=== 완료. 이제 검색이 청크 단위로 동작 (GraphRAG 토대 마련) ===")
