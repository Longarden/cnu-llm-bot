"""크롤링 스케줄러 스텁. freshness_tier에 따라 재크롤 주기 관리."""
FRESHNESS_DAYS = {
    "time_sensitive": 1,
    "semi_static": 7,
    "static": 30,
}


def should_recrawl(last_crawled_at: str, freshness_tier: str) -> bool:
    from datetime import datetime, timezone
    days = FRESHNESS_DAYS.get(freshness_tier, 7)
    try:
        last = datetime.fromisoformat(last_crawled_at).replace(tzinfo=timezone.utc)
        delta = (datetime.now(timezone.utc) - last).days
        return delta >= days
    except Exception:
        return True
