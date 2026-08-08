"""크롤러 전체를 staging 폴더에 새로 긁어서 기존 데이터와 비교 리포트.
기존 data/crawled 는 절대 건드리지 않는다(더미 퇴화 방지).
- 결과: data/crawled_staging/{category}.json
- fallback(더미) 여부 판별: source_url 이 '/fallback' 으로 끝나면 크롤 실패->더미.
- 리포트: data/crawled_staging/_report.json + 콘솔.
실행: python scripts/refresh_crawl_staging.py   (miniconda python)"""
import sys, io, os, json, time, traceback
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from crawlers import ALL_CRAWLERS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD_DIR = os.path.join(ROOT, "data", "crawled")
STAGE_DIR = os.path.join(ROOT, "data", "crawled_staging")
os.makedirs(STAGE_DIR, exist_ok=True)


def is_fallback(docs: list[dict]) -> bool:
    """safe_crawl 더미 판별: 모든 doc의 source_url이 /fallback 이면 더미."""
    if not docs:
        return True
    return all(str(d.get("source_url", "")).endswith("/fallback") for d in docs)


def old_count(category_id: str) -> int:
    """기존 data/crawled 의 해당 카테고리 파일명 추정해 건수 반환."""
    # 크롤러 category_id(예: A_dining)와 파일명(dining.json)이 다를 수 있어
    # data_category 일치로 all 파일에서 세는 게 정확하나, 여기선 파일 직접 매칭 시도.
    for fn in os.listdir(OLD_DIR):
        if not fn.endswith(".json") or fn.startswith("all"):
            continue
        try:
            with open(os.path.join(OLD_DIR, fn), encoding="utf-8") as f:
                data = json.load(f)
            if data and str(data[0].get("data_category", "")) == category_id:
                return len(data)
        except Exception:
            continue
    return 0


report = []
print(f"=== staging 크롤 시작: {len(ALL_CRAWLERS)}개 카테고리 ===\n")

for CrawlerClass in ALL_CRAWLERS:
    crawler = CrawlerClass()
    cid = crawler.category_id
    t0 = time.perf_counter()
    try:
        docs = crawler.safe_crawl()
    except Exception as e:
        docs = []
        print(f"[{cid}] 예외: {e}")
        traceback.print_exc()
    dt = round(time.perf_counter() - t0, 1)

    fb = is_fallback(docs)
    old = old_count(cid)
    out_path = os.path.join(STAGE_DIR, f"{cid}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(docs, f, ensure_ascii=False, indent=2)

    status = "더미(크롤실패)" if fb else "진짜"
    delta = len(docs) - old
    sign = f"+{delta}" if delta >= 0 else str(delta)
    print(f"[{cid}] {status} | 신규 {len(docs)}건 (기존 {old}, {sign}) | {dt}s")
    report.append({
        "category_id": cid,
        "category_name": crawler.category_name,
        "new_count": len(docs),
        "old_count": old,
        "delta": delta,
        "is_fallback": fb,
        "elapsed_s": dt,
    })

with open(os.path.join(STAGE_DIR, "_report.json"), "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

real = [r for r in report if not r["is_fallback"]]
fail = [r for r in report if r["is_fallback"]]
print("\n=== 요약 ===")
print(f"진짜 크롤 성공: {len(real)}/{len(report)} 카테고리")
print(f"신규 총 문서: {sum(r['new_count'] for r in report)}건")
if fail:
    print(f"크롤 실패(더미로 떨어진) 카테고리: {[r['category_id'] for r in fail]}")
print(f"staging 저장 위치: {STAGE_DIR}")
print("기존 data/crawled 는 건드리지 않음. 병합은 사용자 확인 후.")
