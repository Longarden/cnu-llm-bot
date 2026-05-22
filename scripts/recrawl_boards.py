"""빈약 카테고리(admin/scholarship/career/academic) 재크롤 -> all_dedup.json 해당 카테고리 교체 -> 벡터DB 재빌드.
trafilatura 통일 후 '게시물 NNNN' 쓰레기는 본문추출 실패로 자동 제외됨.
실행: python scripts/recrawl_boards.py   (miniconda python)"""
import sys, io, os, json, shutil
from datetime import date
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALL_DEDUP = os.path.join(ROOT, "data", "crawled", "all_dedup.json")

from crawlers.administration import AdministrationCrawler
from crawlers.scholarship import ScholarshipCrawler
from crawlers.career import CareerCrawler
from crawlers.academic import AcademicCrawler
from crawler_pipeline.text_repair import clean_docs

CRAWLERS = [AdministrationCrawler, ScholarshipCrawler, CareerCrawler, AcademicCrawler]
TARGET_CATS = {"C_administration", "D_scholarship", "E_career", "B_academic"}

print("=== 1. 빈약 카테고리 재크롤 (trafilatura 본문) ===")
new_docs = []
for C in CRAWLERS:
    cr = C()
    docs = cr.safe_crawl()
    docs, _ = clean_docs(docs)
    lens = [len(d.get("original_text", "")) for d in docs]
    avg = sum(lens) // max(len(lens), 1)
    print(f"  {cr.category_id}: {len(docs)}건, 평균 {avg}자")
    new_docs.extend(docs)

print("=== 2. all_dedup.json 해당 카테고리 교체 ===")
with open(ALL_DEDUP, encoding="utf-8") as f:
    docs = json.load(f)
kept = [d for d in docs if d.get("data_category") not in TARGET_CATS]
print(f"기존 {len(docs)}건 -> 대상제외 {len(kept)}건 + 새 {len(new_docs)}건")
merged = kept + new_docs

bak = os.path.join(ROOT, "data", "crawled", f"all_dedup.json.boards_bak_{date.today().isoformat()}")
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
print("\n=== 완료. 빈약 카테고리가 본문 포함으로 교체됨 ('게시물 NNNN' 쓰레기 제거) ===")
