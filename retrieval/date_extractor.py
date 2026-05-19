"""한국어 날짜 NER. 8개 패턴 단위 테스트 대상."""
import re
from datetime import datetime, timedelta, date


_PATTERNS = [
    (r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일", "absolute_full"),
    (r"(\d{1,2})월\s*(\d{1,2})일", "absolute_md"),
    (r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})", "iso_date"),
    (r"오늘", "relative_today"),
    (r"내일", "relative_tomorrow"),
    (r"모레", "relative_day_after"),
    (r"이번\s*주", "relative_this_week"),
    (r"다음\s*주", "relative_next_week"),
]


def extract_dates(text: str, reference: date | None = None) -> list[dict]:
    """텍스트에서 날짜 표현 추출. 각 매치에 대해 {pattern, matched, resolved_date} 반환."""
    ref = reference or date.today()
    results = []
    for pattern, name in _PATTERNS:
        for m in re.finditer(pattern, text):
            resolved = _resolve(m, name, ref)
            results.append({"pattern": name, "matched": m.group(), "resolved_date": resolved})
    return results


def _resolve(match: re.Match, pattern_name: str, ref: date) -> str | None:
    try:
        if pattern_name == "absolute_full":
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3))).isoformat()
        if pattern_name == "absolute_md":
            return date(ref.year, int(match.group(1)), int(match.group(2))).isoformat()
        if pattern_name == "iso_date":
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3))).isoformat()
        if pattern_name == "relative_today":
            return ref.isoformat()
        if pattern_name == "relative_tomorrow":
            return (ref + timedelta(days=1)).isoformat()
        if pattern_name == "relative_day_after":
            return (ref + timedelta(days=2)).isoformat()
        if pattern_name == "relative_this_week":
            monday = ref - timedelta(days=ref.weekday())
            return monday.isoformat()
        if pattern_name == "relative_next_week":
            next_monday = ref - timedelta(days=ref.weekday()) + timedelta(weeks=1)
            return next_monday.isoformat()
    except Exception:
        return None
    return None
