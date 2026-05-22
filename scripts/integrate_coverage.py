"""coverage_new.json(거절주제 실데이터)을 all_dedup.json에 병합 -> 중복제거 -> 벡터DB 재빌드.
실행: python scripts/integrate_coverage.py   (miniconda python)"""
import sys, io, os, json, shutil
from datetime import date
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALL = os.path.join(ROOT, "data", "crawled", "all_dedup.json")
NEW = os.path.join(ROOT, "data", "crawled_staging", "coverage_new.json")

old = json.load(open(ALL, encoding="utf-8"))
new = json.load(open(NEW, encoding="utf-8"))
print(f"기존 {len(old)} + 커버리지 {len(new)}")
combined = old + new

from crawler_pipeline.deduplicator import dedup
deduped = dedup(combined, threshold=0.95)
print(f"중복제거 후: {len(deduped)}")

bak = os.path.join(ROOT, "data", "crawled", f"all_dedup.json.cov_bak_{date.today().isoformat()}")
if not os.path.exists(bak):
    shutil.copy(ALL, bak)
json.dump(deduped, open(ALL, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"all_dedup.json 갱신: {len(deduped)}건 (백업 {os.path.basename(bak)})")

print("=== 청킹 + 벡터DB 재빌드 ===")
from embedding.data_loader import load_scoped_docs
from embedding.chunker import chunk_documents
from embedding.vector_store import build_vector_db, count, CHROMA_PATH
import chromadb
chunks = chunk_documents(load_scoped_docs())
print(f"청크 {len(chunks)}개")
client = chromadb.PersistentClient(path=CHROMA_PATH)
try:
    client.delete_collection("cnu_rag")
except Exception as e:
    print(f"삭제 스킵: {e}")
build_vector_db(chunks)
print(f"벡터DB 청크 수: {count()}")
print("=== 완료 ===")
