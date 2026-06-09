# temp verification harness for NoticesCrawler (not committed)
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from crawlers.notices import NoticesCrawler

REQUIRED = ("source_url", "data_category", "last_crawled_at", "valid_until",
            "freshness_tier", "original_text", "title", "content", "date")

c = NoticesCrawler()
docs = c.crawl()
total = len(docs)
fb = sum(1 for d in docs if d.get("is_fallback"))
empty = sum(1 for d in docs if len((d.get("content") or "")) <= len((d.get("title") or "")) + 2)
keys_ok = all(all(k in d for k in REQUIRED) for d in docs)
print(f"TOTAL={total} is_fallback_count={fb} title_only_empty={empty} keys_ok={keys_ok}")
print("--- top 5 (after sort) ---")
for i, d in enumerate(docs[:5]):
    t = (d.get("title") or "")[:60]
    print(f"[{i}] date={d.get('date')} bodylen={len(d.get('content') or '')} title={t}")
    print(f"     url={d.get('source_url')}")
