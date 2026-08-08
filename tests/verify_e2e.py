"""end-to-end 로컬 검증: 검색 + 리랭커 + 거절 + 작은 LLM 답변생성 + 출처.
작은 한국어 모델(Qwen2.5-1.5B) CPU. 7개 샘플(카테고리별 + 도메인밖).
출력 UTF-8 파일."""
import sys, io, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# 작은 모델로 폴백 + 리랭커 활성
os.environ["MODEL_FALLBACK"] = "3b"
os.environ["MODEL_FALLBACK_NAME"] = "Qwen/Qwen2.5-1.5B-Instruct"
os.environ["RERANK"] = "1"

from retrieval import hybrid_retriever as hr
from interface.answer_questions import answer_questions

# 7개 샘플 (카테고리별 1 + 도메인밖)
samples = [
    {"id": "s1", "question": "졸업하려면 몇 학점 필요해?"},
    {"id": "s2", "question": "국가장학금 신청 어떻게 해?"},
    {"id": "s3", "question": "컴퓨터인공지능학부 어디 있어?"},
    {"id": "s4", "question": "백마인턴십이 뭐야?"},
    {"id": "s5", "question": "도서관 운영시간 알려줘"},
    {"id": "s6", "question": "기숙사 입사 신청 어떻게 해?"},
    {"id": "s7", "question": "오늘 날씨 어때?"},  # 도메인 밖 -> 거절 기대
]
qpath = "data/sample_e2e_questions.jsonl"
apath = "data/sample_e2e_answers.jsonl"
with open(qpath, "w", encoding="utf-8") as f:
    for s in samples:
        f.write(json.dumps(s, ensure_ascii=False) + "\n")

print("=== BM25 인덱스 구축 ===")
hr.init_bm25_from_db()

print("=== answer_questions end-to-end (1.5B CPU, 느림) ===")
answer_questions(qpath, apath)

print("\n=== 결과 ===")
with open(apath, encoding="utf-8") as f:
    for line in f:
        r = json.loads(line)
        ans = (r.get("answer", "") or "")[:150].replace("\n", " ")
        rej = r.get("rejected", False)
        src = r.get("sources", [])
        print(f"\n[{r.get('id')}] {r.get('question')}")
        print(f"  거절={rej} 출처={len(src)}개")
        print(f"  답변: {ans}")

print("\n=== E2E 검증 완료 ===")
