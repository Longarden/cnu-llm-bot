"""공지(K_notices)를 본문 포함해서 재크롤 -> all_dedup.json의 공지만 교체 -> 벡터DB 재빌드.
다른 카테고리는 이미 본문 정상이라 건드리지 않음(수술적 교체).
실행: python scripts/recrawl_notices.py   (miniconda python)"""
import sys, io, os, json, shutil
from datetime import date
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALL_DEDUP = os.path.join(ROOT, "data", "crawled", "all_dedup.json")

print("=== 1. 공지 재크롤 (본문 포함, trafilatura) ===")
from crawlers.notices import NoticesCrawler
notices = NoticesCrawler().safe_crawl()
from crawler_pipeline.text_repair import clean_docs
notices, _ = clean_docs(notices)
lens = [len(n.get("original_text", "")) for n in notices]
print(f"공지 {len(notices)}건, 평균 본문 {sum(lens)//max(len(lens),1)}자, 최대 {max(lens) if lens else 0}자")

print("=== 2. all_dedup.json 공지 교체 ===")
with open(ALL_DEDUP, encoding="utf-8") as f:
    docs = json.load(f)
non_notice = [d for d in docs if d.get("data_category") != "K_notices"]
print(f"기존 {len(docs)}건 -> 공지 제외 {len(non_notice)}건 + 새 공지 {len(notices)}건")
merged = non_notice + notices

bak = os.path.join(ROOT, "data", "crawled", f"all_dedup.json.notices_bak_{date.today().isoformat()}")
if not os.path.exists(bak):
    shutil.copy(ALL_DEDUP, bak)
with open(ALL_DEDUP, "w", encoding="utf-8") as f:
    json.dump(merged, f, ensure_ascii=False, indent=2)
print(f"all_dedup.json 갱신: {len(merged)}건 (백업 {os.path.basename(bak)})")

print("=== 3. 청킹 + 벡터DB 재빌드 ===")
from embedding.data_loader import load_scoped_docs
from embedding.chunker import chunk_documents
from embedding.vector_store import build_vector_db, count, CHROMA_PATH
import chromadb
chunks = chunk_documents(load_scoped_docs())
print(f"청크 {len(chunks)}개")
client = chromadb.PersistentClient(path=CHROMA_PATH)
try:
    client.delete_collection("cnu_rag")
    print("기존 컬렉션 삭제")
except Exception as e:
    print(f"삭제 스킵: {e}")
build_vector_db(chunks)
print(f"벡터DB 청크 수: {count()}")
print("\n=== 완료. 공지가 본문 포함으로 교체됨 ===")
