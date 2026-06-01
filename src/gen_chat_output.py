"""배치 챗봇 추론(Task2): data/test_chat.json → outputs/chat_output.json.

입력 : data/test_chat.json   [{"user": "..."}, ...]
출력 : outputs/chat_output.json [{"user": "...", "model": "..."}, ...]
흐름 : 각 user 질문 → src.chat_pipeline.chat_answer (분류 라우팅 + RAG + 생성) → model 답변.

test_chat.json 이 없으면 data/cls/valid.json 의 question 을 user 로 떼서 임시 생성(스모크).

CHAT_STUB=1 이면 생성모델을 돌리지 않고 검색된 청크 요약/스텁으로 model 칸을 채움
(CPU에서 EXAONE 풀로드가 무거울 때 포맷·흐름 검증용).

실행: python src/gen_chat_output.py
"""
import os
import sys
import json
from pathlib import Path

try:
    ROOT = Path(__file__).resolve().parent.parent
except NameError:
    ROOT = Path.cwd()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

TEST_PATH = ROOT / "data" / "test_chat.json"
VALID_PATH = ROOT / "data" / "cls" / "valid.json"
OUT_DIR = ROOT / "outputs"
OUT_PATH = OUT_DIR / "chat_output.json"

STUB = os.environ.get("CHAT_STUB", "0") == "1"


def ensure_test_file():
    """test_chat.json 없으면 valid.json 의 question 을 user 로 떼서 임시 생성."""
    if TEST_PATH.exists():
        return
    if not VALID_PATH.exists():
        raise FileNotFoundError(f"{TEST_PATH} 도 {VALID_PATH} 도 없습니다.")
    with open(VALID_PATH, encoding="utf-8") as f:
        rows = json.load(f)
    test_rows = [{"user": r["question"]} for r in rows if r.get("question")]
    TEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(TEST_PATH, "w", encoding="utf-8") as f:
        json.dump(test_rows, f, ensure_ascii=False, indent=2)
    print(f"[init] test_chat.json 없어 valid 에서 임시 생성: {TEST_PATH} (n={len(test_rows)})")


def _stub_answer(question: str) -> str:
    """생성모델 없이 분류라우팅+검색 청크 요약으로 답 칸 채움(포맷 검증용)."""
    from src.chat_pipeline import route_question
    from interface.answer_questions import _rag_answer, _soft_route_by_category

    label, label_name, categories = route_question(question)
    cat_label = ",".join(categories) if categories else "미분류"
    # _rag_answer 내부 검색을 그대로 쓰되, 생성은 건너뛰고 컨텍스트만 회수
    try:
        from retrieval.hybrid_retriever import retrieve
        from retrieval.reranker import rerank
        docs = retrieve(question, n_results=10)
        docs = _soft_route_by_category(docs, categories or None)
        try:
            top = rerank(question, docs, top_k=2)
        except Exception:
            top = docs[:2]
    except Exception:
        top = []
    snippet = ""
    if top:
        d = top[0]
        meta = d.get("metadata", d)
        snippet = (d.get("text") or d.get("original_text") or "").strip()[:160]
        url = meta.get("source_url", "")
        if url:
            snippet += f"\n출처: {url}"
    return f"[유형:{label_name}/{cat_label}] {snippet or '관련 정보를 찾지 못했습니다.'}"


def main():
    ensure_test_file()

    with open(TEST_PATH, encoding="utf-8") as f:
        test_rows = json.load(f)

    users = [r.get("user", r.get("question", "")) for r in test_rows]
    print(f"[env] CHAT_STUB={STUB}  n={len(users)}  in={TEST_PATH}")

    out = []
    for i, q in enumerate(users):
        print(f"[chat] {i + 1}/{len(users)}: {q[:50]}")
        if STUB:
            model_ans = _stub_answer(q)
        else:
            from src.chat_pipeline import chat_answer
            try:
                model_ans = chat_answer(q)
            except Exception as e:
                model_ans = f"생성 오류: {e}"
        out.append({"user": q, "model": model_ans})

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"[done] {len(out)}건 → {OUT_PATH}")
    for row in out[:3]:
        print("   ", json.dumps(row, ensure_ascii=False)[:200])


if __name__ == "__main__":
    main()
