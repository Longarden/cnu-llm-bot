"""대확장 통합: bvuhtavay 결과(현 all_dedup) + 워커X(자연/공/약/의 학과)
   + 워커Y(학칙PDF/입학처) → dedup → all_dedup.json 갱신 → 벡터DB 재빌드.

전제: bvuhtavay 끝나서 all_dedup.json이 1차 갱신된 상태 + staging 파일 둘 다 존재.
실행: python scripts/integrate_expansion.py  (miniconda python)
"""
import sys, io, os, json, shutil
from datetime import date
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALL = os.path.join(ROOT, "data", "crawled", "all_dedup.json")
NAT = os.path.join(ROOT, "data", "crawled_staging", "departments_natural.json")
REG = os.path.join(ROOT, "data", "crawled_staging", "regulations_admission.json")


def load_or_empty(path, label):
    if not os.path.exists(path):
        print(f"  [{label}] 없음: {path}")
        return []
    d = json.load(open(path, encoding="utf-8"))
    print(f"  [{label}] {len(d)}건")
    return d


print("=== 1. 입력 파일 로드 ===")
base = load_or_empty(ALL, "base(all_dedup)")
nat = load_or_empty(NAT, "natural 학과")
reg = load_or_empty(REG, "학칙+입학처")
combined = base + nat + reg
print(f"  → 합계 {len(combined)}건")

if not nat and not reg:
    print("\n워커 결과가 둘 다 없음. base 그대로 사용하고 재빌드만 수행한다.")
else:
    print("\n=== 2. 인코딩 복구 + 중복제거(bge-m3 0.95) ===")
    from crawler_pipeline.text_repair import clean_docs
    combined, fixed = clean_docs(combined)
    if fixed:
        print(f"  인코딩 복구 {fixed}건")
    from crawler_pipeline.deduplicator import dedup
    deduped = dedup(combined, threshold=0.95)
    print(f"  중복제거: {len(combined)} → {len(deduped)}")

    print("\n=== 3. 백업 + all_dedup.json 갱신 ===")
    bak = os.path.join(ROOT, "data", "crawled",
                       f"all_dedup.json.expand2_bak_{date.today().isoformat()}")
    if os.path.exists(ALL) and not os.path.exists(bak):
        shutil.copy(ALL, bak)
    json.dump(deduped, open(ALL, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"  저장: {len(deduped)}건 (백업 {os.path.basename(bak)})")

print("\n=== 4. 청킹 + 벡터DB 재빌드 ===")
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

print("\n=== 5. 카테고리별 분포(검증) ===")
import json as _json
final = _json.load(open(ALL, encoding="utf-8"))
cat = {}
for x in final:
    c = x.get("data_category", "?")
    cat[c] = cat.get(c, 0) + 1
for c in sorted(cat):
    print(f"  {c:<22} {cat[c]:>4}건")
print(f"\n=== 완료. 통합 후 총 {len(final)}건 ===")
