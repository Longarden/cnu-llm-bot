"""대확장 통합 크롤: 15 카테고리 재크롤(boards bumped N=100, pages=10)
   + 인문사회 학과 캐시(118건) 합침 → dedup → all_dedup.json 갱신 → 벡터DB 재빌드.

실행: python scripts/recrawl_expand_all.py  (miniconda python, 백그라운드 권장)
예상 시간: 30~60분 (plus.cnu.ac.kr 불안정 + 게시판 깊이 4배 증가).
"""
import sys, io, os, json, shutil
from datetime import date
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALL = os.path.join(ROOT, "data", "crawled", "all_dedup.json")
HUMAN = os.path.join(ROOT, "data", "crawled", "departments_humanities_social.json")

print("=== 1. 15 카테고리 재크롤 (boards N=100, pages=10) ===")
from crawlers import ALL_CRAWLERS
results = []
for C in ALL_CRAWLERS:
    cr = C()
    try:
        docs = cr.safe_crawl()
        results.extend(docs)
        print(f"  [{cr.category_id}] {len(docs)}건")
    except Exception as e:
        print(f"  [{cr.category_id}] 실패: {e}")
print(f"  → 크롤 합계 {len(results)}건")

print("=== 2. 인문/사회/경상/사범 학과 캐시 병합 ===")
if os.path.exists(HUMAN):
    human = json.load(open(HUMAN, encoding="utf-8"))
    results.extend(human)
    print(f"  +{len(human)}건 → 누적 {len(results)}")

print("=== 3. 인코딩 복구 + 중복제거(bge-m3 0.95) ===")
from crawler_pipeline.text_repair import clean_docs
results, fixed = clean_docs(results)
if fixed:
    print(f"  인코딩 복구 {fixed}건")
from crawler_pipeline.deduplicator import dedup
deduped = dedup(results, threshold=0.95)
print(f"  중복제거: {len(results)} → {len(deduped)}")

print("=== 4. 백업 후 all_dedup.json 갱신 ===")
bak = os.path.join(ROOT, "data", "crawled", f"all_dedup.json.expand_bak_{date.today().isoformat()}")
if os.path.exists(ALL) and not os.path.exists(bak):
    shutil.copy(ALL, bak)
json.dump(deduped, open(ALL, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"  저장: {len(deduped)}건 (백업 {os.path.basename(bak)})")

print("=== 5. 청킹 + 벡터DB 재빌드 ===")
from embedding.data_loader import load_scoped_docs
from embedding.chunker import chunk_documents
from embedding.vector_store import build_vector_db, count, CHROMA_PATH
import chromadb
chunks = chunk_documents(load_scoped_docs())
print(f"  청크 {len(chunks)}개")
client = chromadb.PersistentClient(path=CHROMA_PATH)
try:
    client.delete_collection("cnu_rag")
except Exception as e:
    print(f"  컬렉션 삭제 스킵: {e}")
build_vector_db(chunks)
print(f"  벡터DB 청크수: {count()}")
print("=== 완료 ===")
