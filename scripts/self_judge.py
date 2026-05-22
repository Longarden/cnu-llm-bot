"""Claude-as-judge 대용: eval 답변을 규칙기반으로 3축 채점(0~5) + 약점 진단.
진짜 LLM judge(API) 없이 baseline 점수 산출용. testset 카테고리로 거절 정답 여부 판정.
실행: python scripts/self_judge.py [answers.json]  (기본 Downloads/eval_results.json)
"""
import sys, io, json, re, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ANS = sys.argv[1] if len(sys.argv) > 1 else "C:/Users/dmsak/Downloads/eval_results.json"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTSET = os.path.join(ROOT, "data", "testset.jsonl")

data = json.load(open(ANS, encoding="utf-8"))
details = data["details"] if isinstance(data, dict) and "details" in data else data

# testset에서 질문->카테고리 매핑 (거절 정답 판정용)
qcat = {}
with open(TESTSET, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line:
            it = json.loads(line)
            qcat[it["question"]] = it.get("category", "")

REJECT = ["제공된 자료에 해당 정보가 없습니다", "범위를 벗어난", "유효 기간", "지났습니다"]
SRC = re.compile(r"출처\s*[:：].*?(https?://|portal|plus|cnu)", re.S)
LEAK = re.compile(r"\[?\s*참고자료\s*\d+|업데이트\s*[:：].*유효기간|hasn't|provided information")

def is_reject(a):
    return any(r in a for r in REJECT) and len(a) < 200

def score(item):
    a = item.get("answer", "") or ""
    cat = qcat.get(item.get("question", ""), "")
    ood = (cat == "out_of_domain")
    rej = is_reject(a)
    leak = bool(LEAK.search(a))
    has_src = bool(SRC.search(a))
    if ood:
        if rej or "범위를 벗어난" in a:
            return 5, 5, 5, "OOD 올바른 거절"
        return 2, 2, 1, "OOD인데 답해버림(거절했어야)"
    # in-domain
    if rej:
        return 2, 2, 4, "도메인내 거절(정직하나 답변 실패)"
    # answered
    acc = 4 if has_src else 3
    rel = 4
    dom = 4
    note = "답변"
    if leak:
        rel -= 1; dom -= 1; note = "답변(출처누출/메타 지저분)"
    if not has_src:
        dom -= 1; note += "+출처없음"
    return acc, rel, dom, note

rows = [(it, *score(it)) for it in details]
n = len(rows)
import statistics as st
A = st.mean(r[1] for r in rows); R = st.mean(r[2] for r in rows); D = st.mean(r[3] for r in rows)
print(f"=== 규칙기반 self-judge: {n}개 ===")
print(f"accuracy {A:.2f} / relevance {R:.2f} / domain {D:.2f} / overall {(A+R+D)/3:.2f}  (0~5)")

# 버킷
buckets = {}
for it, a, r, d, note in rows:
    buckets[note] = buckets.get(note, 0) + 1
print("\n결과 분포:")
for k, v in sorted(buckets.items(), key=lambda x: -x[1]):
    print(f"  {v:>3}  {k}")

# 카테고리별 평균
bycat = {}
for it, a, r, d, note in rows:
    c = qcat.get(it.get("question", ""), "?")
    bycat.setdefault(c, []).append((a + r + d) / 3)
print("\n카테고리별 overall:")
for c in sorted(bycat, key=lambda x: st.mean(bycat[x])):
    L = bycat[c]
    print(f"  {c:<18} {st.mean(L):.2f}  ({len(L)}개)")
