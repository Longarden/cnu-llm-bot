"""LLM 없이 버그 3개만 빠르게 검증.
검색(date_filter 후처리) + 리랭커(CrossEncoder) + 거절판정만 확인.
LLM 다운로드/추론 없으니 수초~수십초로 끝남(임베딩/리랭커는 캐시 사용).
출력 UTF-8."""
import sys, io, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

os.environ["RERANK"] = "1"

from retrieval import hybrid_retriever as hr
from retrieval.date_extractor import extract_dates
from retrieval.reranker import rerank
from generation.rejector import check_rejection

samples = [
    ("s1", "졸업하려면 몇 학점 필요해?",        False),
    ("s2", "국가장학금 신청 어떻게 해?",          False),
    ("s3", "컴퓨터인공지능학부 어디 있어?",       False),
    ("s4", "백마인턴십이 뭐야?",                  False),
    ("s5", "도서관 운영시간 알려줘",              False),
    ("s6", "기숙사 입사 신청 어떻게 해?",         False),
    ("s7", "오늘 날씨 어때?",                     True),   # 도메인 밖 -> 거절 기대
]

print("=== BM25 인덱스 구축 ===")
hr.init_bm25_from_db()

print("\n=== 검색 + 리랭커 + 거절 (LLM 제외) ===")
ok = 0
for sid, q, expect_reject in samples:
    # 날짜 -> date_filter (버그1 경로)
    dates = extract_dates(q)
    date_filter = None
    if dates and dates[0].get("resolved_date"):
        date_filter = {"valid_until": {"$gte": dates[0]["resolved_date"]}}

    docs = hr.retrieve(q, n_results=10, date_filter=date_filter)   # 버그1: 크래시 없어야 함
    top = rerank(q, docs, top_k=3)                                 # 버그2: CrossEncoder
    rej = check_rejection(q, top)                                  # 버그3: 과잉거절 아님

    dense = max([float(d.get("dense_score", 0) or 0) for d in top], default=0)
    sparse = max([float(d.get("sparse_score", 0) or 0) for d in top], default=0)
    cat = top[0].get("data_category", "?") if top else "-"
    txt = (top[0].get("original_text", "") or top[0].get("text", ""))[:45].replace("\n", " ") if top else ""

    hit = (rej.rejected == expect_reject)
    ok += 1 if hit else 0
    mark = "OK " if hit else "!! "
    print(f"\n[{sid}] {q}")
    print(f"  {mark}거절={rej.rejected}(기대 {expect_reject}) 사유={rej.reason or '-'} "
          f"dense={dense:.3f} sparse={sparse:.2f}")
    print(f"  top: ({cat}) {txt}")

print(f"\n=== 결과: {ok}/{len(samples)} 기대대로 ===")
print("(s1~s6 거절 안함, s7만 거절이면 버그3 해결. 크래시 없으면 버그1, 리랭커 점수 있으면 버그2 해결)")
