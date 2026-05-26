"""대확장 빠른 통합: title-hash 기반 dedup(O(n))로 staging 두 개 합침.

bge-m3 dedup이 CPU에서 너무 오래 걸려서 이걸로 대체한다.
정책: 정규화 title이 같으면 content가 더 긴 쪽만 유지.

실행: python scripts/integrate_fast.py  (miniconda python)
"""
import sys, io, os, json, shutil, re
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


def norm_title(t: str) -> str:
    t = (t or "").strip().lower()
    t = re.sub(r"\s+", " ", t)
    return t


def dedup_by_title(docs: list[dict]) -> list[dict]:
    """키 = (정규화 title, source_url). 다른 url이면 다른 문서로 본다."""
    best: dict[tuple, dict] = {}
    for d in docs:
        t = norm_title(d.get("title", ""))
        url = (d.get("source_url") or "").strip()
        if not t:
            continue
        key = (t, url)
        prev = best.get(key)
        if prev is None or len(d.get("original_text", "")) > len(prev.get("original_text", "")):
            best[key] = d
    return list(best.values())


print("=== 1. 입력 파일 로드 ===")
base = load_or_empty(ALL, "base(all_dedup)")
nat = load_or_empty(NAT, "natural 학과")
reg = load_or_empty(REG, "학칙+입학처")
combined = base + nat + reg
print(f"  → 합계 {len(combined)}건")

print("\n=== 2. 인코딩 복구 + title-hash dedup ===")
from crawler_pipeline.text_repair import clean_docs
combined, fixed = clean_docs(combined)
if fixed:
    print(f"  인코딩 복구 {fixed}건")
deduped = dedup_by_title(combined)
print(f"  title-hash dedup: {len(combined)} → {len(deduped)}")

print("\n=== 3. 백업 + all_dedup.json 갱신 ===")
bak = os.path.join(ROOT, "data", "crawled",
                   f"all_dedup.json.expand2_bak_{date.today().isoformat()}")
if os.path.exists(ALL) and not os.path.exists(bak):
    shutil.copy(ALL, bak)
json.dump(deduped, open(ALL, "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print(f"  저장: {len(deduped)}건 (백업 {os.path.basename(bak)})")

print("\n=== 4. 청킹/벡터DB 재빌드는 스킵 (GPU 환경에서 별도 수행) ===")

print("\n=== 5. 카테고리별 분포(검증) ===")
final = json.load(open(ALL, encoding="utf-8"))
cat = {}
for x in final:
    c = x.get("data_category", "?")
    cat[c] = cat.get(c, 0) + 1
for c in sorted(cat):
    print(f"  {c:<22} {cat[c]:>4}건")
print(f"\n=== 완료. 통합 후 총 {len(final)}건 ===")
