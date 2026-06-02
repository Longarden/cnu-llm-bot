"""멀티GPU bge-m3 임베딩으로 벡터DB 빌드 (P100 8장 서버용 — 인덱스 빌드 ~8배 가속).

- GPU 여러 장이면 SentenceTransformer 멀티프로세스 풀로 분산 임베딩(8장 → 대략 8배).
- GPU 1장/CPU면 자동으로 일반 encode 폴백.
- 결과 chroma_db/ 는 단일GPU 빌드본과 포맷 동일 → 콜랩 T4/조교 환경에서 그대로 복사·로드 가능.
  (전략: P100서 한 번 빌드 → chroma_db 를 구글드라이브/깃에 올림 → 콜랩은 15분 재빌드 없이 로드만)

실행(P100 서버): python scripts/rebuild_index_multigpu.py
빌드 후: chroma_db/ 디렉토리를 드라이브/저장소로 복사해 콜랩에서 재사용.
"""
import sys, io, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
except Exception:
    pass

from embedding.data_loader import load_scoped_docs
from embedding.chunker import chunk_documents
from embedding.vector_store import CHROMA_PATH, REQUIRED_METADATA, _get_collection, count

print("=== 1. 데이터 로드 + 청킹 ===")
docs = load_scoped_docs()
chunks = chunk_documents(docs)
print(f"문서 {len(docs)}건 → 청크 {len(chunks)}개")

texts, metadatas, ids = [], [], []
for i, doc in enumerate(chunks):
    text = doc.get("original_text", "")
    if not text:
        continue
    metadatas.append({k: str(doc.get(k, "")) for k in REQUIRED_METADATA})
    texts.append(text)
    ids.append(f"doc_{i}")
print(f"임베딩 대상 {len(texts)}건")

print("=== 2. 기존 컬렉션 리셋 ===")
import chromadb
client = chromadb.PersistentClient(path=CHROMA_PATH)
try:
    client.delete_collection("cnu_rag")
    print("기존 컬렉션 삭제")
except Exception as e:
    print(f"삭제 스킵: {e}")

print("=== 3. bge-m3 임베딩 (멀티GPU 자동) ===")
import torch
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("BAAI/bge-m3")
n_gpu = torch.cuda.device_count()
print(f"감지된 GPU 수: {n_gpu}")

if n_gpu > 1:
    print(f"멀티GPU 분산 임베딩 시작({n_gpu}장)...")
    pool = model.start_multi_process_pool()  # 가용 CUDA 디바이스 전부 사용
    try:
        embeddings = model.encode_multi_process(
            texts, pool, batch_size=64, normalize_embeddings=True,
        )
    finally:
        model.stop_multi_process_pool(pool)
else:
    print("단일 디바이스 임베딩(폴백)...")
    embeddings = model.encode(
        texts, batch_size=64, normalize_embeddings=True, show_progress_bar=True,
    )

embeddings = embeddings.tolist()

print("=== 4. chroma 저장 ===")
collection = _get_collection()
B = 1000
for s in range(0, len(texts), B):
    collection.add(
        documents=texts[s:s + B],
        embeddings=embeddings[s:s + B],
        metadatas=metadatas[s:s + B],
        ids=ids[s:s + B],
    )
    print(f"  {min(s + B, len(texts))}/{len(texts)} 저장")

print(f"\n=== 완료. 벡터DB 청크 수: {count()} ===")
print("이제 chroma_db/ 를 드라이브/저장소로 복사해 콜랩에서 재사용하세요.")
