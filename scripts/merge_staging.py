"""기존 all_dedup.json + staging 합집합 -> 중복제거 -> all_dedup.json 갱신 -> 벡터DB 재빌드.
- 기존 all_dedup.json 은 all_dedup_backup_{날짜}.json 으로 백업.
- dedup: deduplicator.dedup (bge-m3 코사인 0.95).
- 벡터DB는 기존 컬렉션 삭제 후 새로 빌드(중복 추가 방지).
실행: python scripts/merge_staging.py   (miniconda python)"""
import sys, io, os, json, shutil
from datetime import date
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALL_DEDUP = os.path.join(ROOT, "data", "crawled", "all_dedup.json")
STAGE_DIR = os.path.join(ROOT, "data", "crawled_staging")


def cat_dist(docs):
    d = {}
    for x in docs:
        c = x.get("data_category", "?")
        d[c] = d.get(c, 0) + 1
    return dict(sorted(d.items()))


# 1. 기존 로드
with open(ALL_DEDUP, encoding="utf-8") as f:
    old_docs = json.load(f)
print(f"기존 all_dedup.json: {len(old_docs)}건")

# 2. staging 로드 (_report.json 제외)
stage_docs = []
for fn in sorted(os.listdir(STAGE_DIR)):
    if not fn.endswith(".json") or fn.startswith("_"):
        continue
    with open(os.path.join(STAGE_DIR, fn), encoding="utf-8") as f:
        stage_docs.extend(json.load(f))
print(f"staging 합계: {len(stage_docs)}건")

# 3. 합집합
combined = old_docs + stage_docs
print(f"합집합(중복제거 전): {len(combined)}건")

# 4. 중복제거 (bge-m3)
from crawler_pipeline.deduplicator import dedup
deduped = dedup(combined, threshold=0.95)
print(f"중복제거 후: {len(deduped)}건")
print("카테고리 분포:")
for c, n in cat_dist(deduped).items():
    print(f"  {c}: {n}")

# 5. 백업 후 갱신
backup = os.path.join(ROOT, "data", "crawled", f"all_dedup_backup_{date.today().isoformat()}.json")
shutil.copy(ALL_DEDUP, backup)
print(f"\n기존 백업: {backup}")
with open(ALL_DEDUP, "w", encoding="utf-8") as f:
    json.dump(deduped, f, ensure_ascii=False, indent=2)
print(f"all_dedup.json 갱신 완료: {len(deduped)}건")

# 6. 벡터DB 재빌드 (기존 컬렉션 삭제 후)
print("\n=== 벡터DB 재빌드 ===")
from embedding.vector_store import build_vector_db, count, CHROMA_PATH
import chromadb
client = chromadb.PersistentClient(path=CHROMA_PATH)
try:
    client.delete_collection("cnu_rag")
    print("기존 컬렉션 삭제")
except Exception as e:
    print(f"컬렉션 삭제 스킵: {e}")
build_vector_db(deduped)
print(f"벡터DB 청크 수: {count()}건")
print("\n=== 완료. 이제 검색이 새 데이터(공지 포함) 반영함 ===")
