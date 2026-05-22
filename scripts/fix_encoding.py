"""저장된 크롤 데이터의 인코딩 깨짐을 1회 복구해서 파일에 반영.
all_dedup.json + 개별 카테고리 파일 대상. 백업 후 덮어씀.
실행: python scripts/fix_encoding.py   (miniconda python)"""
import sys, io, os, json, glob, shutil
from datetime import date
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from crawler_pipeline.text_repair import clean_docs

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CRAWLED = os.path.join(ROOT, "data", "crawled")

total_fixed = 0
for path in glob.glob(os.path.join(CRAWLED, "*.json")):
    fn = os.path.basename(path)
    if fn.startswith("all_dedup_backup_"):
        continue
    with open(path, encoding="utf-8") as f:
        docs = json.load(f)
    if not isinstance(docs, list):
        continue
    docs, fixed = clean_docs(docs)
    if fixed:
        bak = path + f".bak_{date.today().isoformat()}"
        if not os.path.exists(bak):
            shutil.copy(path, bak)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(docs, f, ensure_ascii=False, indent=2)
        print(f"[{fn}] {fixed}건 복구 -> 저장 (백업 {os.path.basename(bak)})")
        total_fixed += fixed
    else:
        print(f"[{fn}] 깨진 것 없음")

print(f"\n총 {total_fixed}건 인코딩 복구 완료.")
