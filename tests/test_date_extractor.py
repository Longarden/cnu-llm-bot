"""한국어 날짜 NER 8개 패턴 단위 테스트 (AC6)."""
import pytest
from datetime import date, timedelta
from retrieval.date_extractor import extract_dates


REF = date(2026, 5, 19)


def test_absolute_full():
    results = extract_dates("2026년 5월 19일에 수업이 있어요", REF)
    assert any(r["resolved_date"] == "2026-05-19" for r in results)


def test_absolute_md():
    results = extract_dates("5월 19일 수강신청 마감이에요", REF)
    assert any(r["resolved_date"] == "2026-05-19" for r in results)


def test_iso_date():
    results = extract_dates("2026-05-19 시험이에요", REF)
    assert any(r["resolved_date"] == "2026-05-19" for r in results)


def test_today():
    results = extract_dates("오늘 학식 메뉴가 뭐예요?", REF)
    assert any(r["resolved_date"] == "2026-05-19" for r in results)


def test_tomorrow():
    results = extract_dates("내일 도서관 몇 시까지예요?", REF)
    expected = (REF + timedelta(days=1)).isoformat()
    assert any(r["resolved_date"] == expected for r in results)


def test_day_after():
    results = extract_dates("모레 셔틀 있나요?", REF)
    expected = (REF + timedelta(days=2)).isoformat()
    assert any(r["resolved_date"] == expected for r in results)


def test_this_week():
    results = extract_dates("이번 주 행사 일정 알려주세요", REF)
    monday = (REF - timedelta(days=REF.weekday())).isoformat()
    assert any(r["resolved_date"] == monday for r in results)


def test_next_week():
    results = extract_dates("다음 주 공지사항 있나요?", REF)
    next_monday = (REF - timedelta(days=REF.weekday()) + timedelta(weeks=1)).isoformat()
    assert any(r["resolved_date"] == next_monday for r in results)
