"""
교수님 제출 인터페이스 (AC12).
questions.jsonl / .json / .csv → answers.jsonl
"""

import argparse
import csv
import json
import re
import time
from pathlib import Path
from typing import Optional


# 출처 포함 여부 확인 정규식
_SOURCE_PATTERN = re.compile(r"출처\s*:")


def _clean_answer(answer: str) -> str:
    """모델이 베껴 쓴 출처/메타/참고자료 토큰 제거 → 본문만 남김.

    작은 LLM이 컨텍스트의 '[참고자료 N]', '출처: ... | 업데이트: ...'를 그대로
    베껴 써서 출처 누출·중복이 생김. 후처리로 정리하고 깨끗한 출처를 따로 붙인다.
    """
    # 인라인 [참고자료 N] / 참고자료 N 토큰 제거
    answer = re.sub(r"\[?\s*참고자료\s*\d+\s*\]?", "", answer)
    # 첫 출처 마커(출처: 또는 [출처)부터 끝까지 잘라냄 (모델이 붙인 출처 꼬리 제거)
    answer = re.split(r"\n?\s*(?:출처\s*[:：]|\[출처)", answer, maxsplit=1)[0]
    # 잔재 메타 줄(업데이트/유효기간/마지막 업데이트/날짜:) 제거
    kept = []
    for ln in answer.split("\n"):
        s = ln.strip().lstrip("[(-* ")
        if re.match(r"^(업데이트|유효기간|마지막\s*업데이트|날짜)\s*[:：]", s):
            continue
        kept.append(ln)
    return "\n".join(kept).strip()


def _load_questions(path: str) -> list[dict]:
    """JSONL / JSON / CSV 다중 포맷 지원 어댑터."""
    p = Path(path)
    suffix = p.suffix.lower()

    if suffix == ".csv":
        with open(path, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            return list(reader)

    with open(path, encoding="utf-8") as f:
        content = f.read().strip()

    # JSON 배열 형식
    if content.startswith("["):
        items = json.loads(content)
        return items if isinstance(items, list) else [items]

    # JSONL 형식 (한 줄씩)
    result = []
    for line in content.splitlines():
        line = line.strip()
        if line:
            result.append(json.loads(line))
    return result


def _rag_answer(
    question: str,
    llm=None,
    retriever=None,
    return_context: bool = False,
):
    """단일 질문 RAG 파이프라인 실행."""
    from retrieval.date_extractor import extract_dates
    from generation.rejector import check_rejection
    from generation.prompt import build_user_prompt, build_few_shot_messages, SYSTEM_PROMPT

    # 날짜 추출 → 메타데이터 필터
    dates = extract_dates(question)
    date_filter = None
    if dates and dates[0].get("resolved_date"):
        date_filter = {"valid_until": {"$gte": dates[0]["resolved_date"]}}

    # 검색
    docs = []
    top_docs = []
    if retriever is not None:
        try:
            docs = retriever.retrieve(question, k=5)
            top_docs = docs
        except Exception:
            docs = []
    else:
        try:
            from retrieval.hybrid_retriever import retrieve
            docs = retrieve(question, n_results=10, date_filter=date_filter)
        except Exception:
            docs = []
        try:
            from retrieval.reranker import rerank
            top_docs = rerank(question, docs, top_k=3)
        except Exception:
            top_docs = docs[:3] if docs else []

    # 거절 판정
    rejection = check_rejection(question, top_docs)
    if rejection.rejected:
        if return_context:
            return rejection.message, top_docs, True
        return rejection.message

    # 프롬프트 구성
    chunks_for_prompt = []
    sources = []
    for d in top_docs:
        meta = d.get("metadata", d)
        chunks_for_prompt.append({
            "text": d.get("text", d.get("original_text", "")),
            "source_url": meta.get("source_url", ""),
            "last_crawled_at": meta.get("last_crawled_at", ""),
            "valid_until": meta.get("valid_until", ""),
        })
        url = meta.get("source_url", "")
        if url:
            sources.append(url)

    user_prompt = build_user_prompt(question, chunks_for_prompt)
    full_prompt = SYSTEM_PROMPT + "\n\n" + user_prompt

    # 생성
    if llm is not None:
        try:
            from generation.prompt import build_few_shot_messages
            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            messages += build_few_shot_messages()
            messages.append({"role": "user", "content": build_user_prompt(question, chunks_for_prompt)})
            answer = llm(messages)[0]["generated_text"][-1]["content"]
        except Exception:
            answer = full_prompt  # 폴백
    else:
        try:
            from generation.llm import generate
            answer = generate(full_prompt, system_prompt=SYSTEM_PROMPT)
        except Exception as e:
            answer = f"생성 오류: {e}"

    # 모델이 베껴 쓴 지저분한 출처/메타/참고자료 토큰 제거 후 깔끔한 출처 1줄로 통일
    answer = _clean_answer(answer)

    # CRAG ambiguous 단서 추가 (부분 매칭일 때 - 거절은 아님)
    if getattr(rejection, "caveat", ""):
        answer = answer.rstrip() + f"\n\n※ {rejection.caveat}"

    # 깨끗한 출처 1줄 (실제 URL만, 중복 제거)
    if sources:
        answer = answer.rstrip() + "\n\n출처: " + ", ".join(sources[:3])

    if return_context:
        return answer, top_docs, False
    return answer


def answer_questions(
    questions_path: str,
    answers_path: Optional[str] = None,
    llm=None,
    retriever=None,
) -> str:
    """
    questions.jsonl 읽기 → 각 질문 RAG 실행 → answers.jsonl 쓰기.

    Args:
        questions_path: 입력 파일 경로 (JSONL/JSON/CSV)
        answers_path: 출력 파일 경로 (None 이면 자동 생성)
        llm: 생성 모델 파이프라인 (None 이면 generation.llm.generate 사용)
        retriever: 검색기 객체 (None 이면 retrieval.hybrid_retriever.retrieve 사용)

    Returns:
        answers_path (AC12 인터페이스)
    """
    if answers_path is None:
        p = Path(questions_path)
        answers_path = str(p.parent / p.name.replace("questions", "answers").replace(p.suffix, "_answers.jsonl"))

    Path(answers_path).parent.mkdir(parents=True, exist_ok=True)

    questions = _load_questions(questions_path)

    answers = []
    for i, item in enumerate(questions):
        question = item.get("question", item.get("q", str(item)))
        print(f"[answer_questions] {i+1}/{len(questions)}: {question[:50]}")
        start = time.perf_counter()
        answer, top_docs, rejected = _rag_answer(question, llm=llm, retriever=retriever, return_context=True)
        elapsed_ms = round((time.perf_counter() - start) * 1000)

        sources = []
        for d in top_docs:
            meta = d.get("metadata", d)
            url = meta.get("source_url", "")
            if url and url not in sources:
                sources.append(url)

        answers.append({
            "id": item.get("id", i + 1),
            "question": question,
            "answer": answer,
            "sources": sources,
            "rejected": rejected,
            "latency_ms": elapsed_ms,
        })

    with open(answers_path, "w", encoding="utf-8") as f:
        for a in answers:
            f.write(json.dumps(a, ensure_ascii=False) + "\n")

    print(f"[answer_questions] {len(answers)}개 답변 저장 -> {answers_path}")
    return answers_path


def main():
    parser = argparse.ArgumentParser(description="CNU RAG 챗봇 배치 답변 생성")
    parser.add_argument("--questions", required=True, help="입력 질문 파일 (JSONL/JSON/CSV)")
    parser.add_argument("--answers", default=None, help="출력 답변 파일 (JSONL)")
    args = parser.parse_args()
    answer_questions(args.questions, args.answers)


if __name__ == "__main__":
    main()
