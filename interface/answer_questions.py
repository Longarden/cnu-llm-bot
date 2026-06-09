"""
교수님 제출 인터페이스 (AC12).
questions.jsonl / .json / .csv → answers.jsonl
"""
from __future__ import annotations
import argparse
import csv
import json
import re
import time
from pathlib import Path
from typing import Optional


# 출처 포함 여부 확인 정규식
_SOURCE_PATTERN = re.compile(r"출처\s*:")


# 한글/중국어(한자) 판별용. 일부 LLM이 가끔 중국어로 코드스위칭하는데 프롬프트 지시만으론
# 완전히 막히지 않아, 생성 후처리로 '중국어로 보이는 줄'(한자 다수 + 한글 0)을 결정론적 제거.
_HANGUL_RE = re.compile(r"[가-힣]")
_CJK_RE = re.compile(r"[一-鿿]")


def _strip_foreign_lines(text: str) -> str:
    """중국어 누출 줄 제거. 한글이 한 글자도 없고 한자가 2개 이상인 줄을 버린다.

    한국어 줄(한글 포함)이나 한자가 살짝 섞인 한국어(예: 學점)는 그대로 둔다.
    과삭제 방지: 전부 지워지면 원본을 반환.
    """
    out = []
    for ln in text.split("\n"):
        if len(_CJK_RE.findall(ln)) >= 2 and not _HANGUL_RE.search(ln):
            continue  # 중국어 줄로 판단 → 제거
        out.append(ln)
    cleaned = "\n".join(out).strip()
    return cleaned if cleaned else text


# 본문에 새는 URL(http/https/www/맨도메인.ac.kr 등). 규칙7: 출처는 시스템이 따로 붙임.
# 타대학 환각 링크(nsugang.hanseo.ac.kr=한서대, scnu.ac.kr=순천대 등)도 여기서 결정론적으로 사살.
_URL_RE = re.compile(
    r"(?:https?://[^\s)\]>\"'）】」]+"
    r"|www\.[^\s)\]>\"'）】」]+"
    # 스킴 없는 기관 도메인만(ac.kr/go.kr). 이메일 local-part·파일명·버전 오삭제 방지 위해
    # 앞에 단어문자/@가 오면 매칭 안 함. (.com/.kr 등 일반 TLD는 제외 — http/www 분기가 잡음)
    r"|(?<![\w@])[A-Za-z0-9][A-Za-z0-9.\-]*\.(?:ac\.kr|go\.kr)(?:/[^\s)\]>\"'）】」]*)?)",
    re.IGNORECASE,
)


def _strip_markdown(text: str) -> str:
    """마크다운 기호 제거 → 평문. UI 버블이 textContent(평문)라 #·*·`·[](링크)가
    그대로 노출돼 지저분해지는 것을 막는다. 불릿은 '- '로 통일.
    """
    # [라벨](url) → 라벨  (인라인 링크의 url 제거, 라벨만 남김)
    text = re.sub(r"\[([^\]\n]+)\]\((?:[^)\n]*)\)", r"\1", text)
    # 이미지/빈 링크 잔재 제거
    text = re.sub(r"!\[[^\]\n]*\]\([^)\n]*\)", "", text)
    out = []
    for ln in text.split("\n"):
        # 머리말 #, 인용 > 제거
        ln = re.sub(r"^\s{0,3}#{1,6}\s*", "", ln)
        ln = re.sub(r"^\s{0,3}>\s?", "", ln)
        # 불릿 통일: 줄머리 *, •, · → -
        ln = re.sub(r"^(\s*)[*•·]\s+", r"\1- ", ln)
        out.append(ln)
    text = "\n".join(out)
    # 굵게/기울임/코드 마커 제거 (** __ ` *), 잔재 토큰 정리
    text = text.replace("**", "").replace("__", "").replace("`", "")
    text = re.sub(r"(?<!\s)\*(?!\s)|\*", "", text)  # 남은 * 제거(불릿은 이미 -로 변환됨)
    return text


def _clean_answer(answer: str) -> str:
    """모델이 베껴 쓴 출처/메타/참고자료/마크다운/본문URL 제거 → 본문만 남김.

    작은 LLM(2.4B)이 컨텍스트의 '[참고자료 N]', '출처: ... | 업데이트: ...', 마크다운 헤더,
    타대학 환각 URL 등을 그대로 써서 누출·중복·오링크가 생김. 프롬프트 규칙만으론 안 지켜져
    결정론적 후처리로 못박는다. 깨끗한 출처는 호출부가 따로 1줄 붙인다(규칙7).
    """
    # 1) 중국어 누출 줄 먼저 제거(한국어 전용 챗봇)
    answer = _strip_foreign_lines(answer)
    # 2) 인라인 [참고자료 N] / 참고자료 N 토큰 제거
    answer = re.sub(r"\[?\s*참고자료\s*\d+\s*\]?", "", answer)
    # 3) 첫 '출처/출처 URL/참고문헌' 마커부터 끝까지 잘라냄(모델이 붙인 꼬리 제거 → 우리가 깨끗한 출처 재부착).
    #    **출처**: / ##출처 / 출처: / 출처 URL: / [출처 등 마크다운·변형도 모두 잡는다.
    answer = re.split(
        r"\n?\s*(?:[#*\s]*출처\s*(?:URL|url|링크)?[#*\s]*[:：]|\[출처|##+\s*출처|참고\s*문헌\s*[:：])",
        answer, maxsplit=1,
    )[0]
    # 4) 마크다운 기호 제거(평문화)
    answer = _strip_markdown(answer)
    # 5) 본문에 남은 URL 전부 제거(규칙7 + 타대학 환각 링크 사살). URL만 있던 줄은 통째 버림.
    kept = []
    for ln in answer.split("\n"):
        s = ln.strip().lstrip("[(-* ")
        # 잔재 메타 줄(업데이트/유효기간/마지막 업데이트/날짜:) 제거
        if re.match(r"^(업데이트|유효기간|마지막\s*업데이트|날짜)\s*[:：]", s):
            continue
        stripped = _URL_RE.sub("", ln)
        had_url = (ln.strip() != stripped.strip())
        if had_url:
            # URL 빠진 자리의 빈 괄호/대괄호, 줄끝 여는 괄호 정리
            stripped = re.sub(r"[\(\[【（]\s*[)\]】）]?|\s*[)\]】）]\s*$", " ", stripped)
        # URL 떼고 남은 게 라벨/기호뿐이면(예: '출처 URL: ', '- 주소:', '()') 줄 버림
        residue = re.sub(r"[\s\-*:：()\[\]·•]|출처|URL|링크|바로가기|주소|사이트|페이지|홈페이지|here|link",
                         "", stripped, flags=re.IGNORECASE)
        if not residue and had_url:
            continue  # URL 때문에 존재하던 줄 → 제거
        kept.append(re.sub(r"[ \t]{2,}", " ", stripped).rstrip())
    answer = "\n".join(kept)
    # 6) 빈 줄 3개+ → 2개로, 양끝 정리
    answer = re.sub(r"\n{3,}", "\n\n", answer).strip()
    return answer


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


def _soft_route_by_category(docs: list, category_hint, min_keep: int = 2) -> list:
    """분류기 카테고리 힌트로 검색결과를 소프트 라우팅.

    category_hint 는 단일 카테고리 문자열 또는 카테고리 집합/리스트(여러 data_category)를
    받는다. 청크의 data_category 가 힌트 중 하나라도 매칭되면 앞으로 끌어올리고,
    매칭 청크가 min_keep 이상이면 그 카테고리들을 우선 사용. 빈약하면(min_keep 미만)
    전체를 그대로 둠(폴백). 힌트 없으면 원본 그대로 반환 → 기존 동작 불변.

    하위호환: 문자열을 넘기면 단일 원소 집합으로 처리(기존 호출부 그대로 동작).
    """
    if not category_hint or not docs:
        return docs
    # 문자열/리스트/집합 모두 허용 → 매칭용 집합으로 정규화
    if isinstance(category_hint, str):
        hint_set = {category_hint}
    else:
        hint_set = {c for c in category_hint if c}
    if not hint_set:
        return docs
    matched, others = [], []
    for d in docs:
        meta = d.get("metadata", d) if isinstance(d, dict) else {}
        cat = (meta.get("data_category") or (d.get("data_category") if isinstance(d, dict) else "")) or ""
        (matched if cat in hint_set else others).append(d)
    if len(matched) >= min_keep:
        # 카테고리 매칭 우선, 나머지는 뒤에 폴백으로 유지
        return matched + others
    return docs  # 빈약 → 전체 폴백


# 대학원 자료 식별 힌트(URL/제목). 학부생 대상 챗봇이라 대학원 규정이 학부 답을 가리지 않게 후순위로.
_GRAD_URL_HINTS = ("/grad", "graduate", "/gradsch", "daehakwon")
_GRAD_TITLE_HINTS = ("대학원", "전문대학원", "특수대학원")


def _deprioritize_grad(docs: list) -> list:
    """대학원 표시가 있는 청크를 뒤로 미룬다(드롭은 안 함, 폴백 유지).

    예: 전과 질문에 medicine.cnu/grad(대학원 전과 규정)가 1위로 와서 학부 답을 가리는 문제 해소.
    학부 자료가 우선 노출되고, 대학원 자료는 학부에 답이 없을 때만 폴백으로 쓰인다.
    """
    if not docs:
        return docs

    def _is_grad(d):
        if not isinstance(d, dict):
            return False
        meta = d.get("metadata", d)
        url = (meta.get("source_url", "") or "").lower()
        title = (d.get("title", "") or meta.get("title", "") or "")
        if any(h in url for h in _GRAD_URL_HINTS):
            return True
        return any(h in title for h in _GRAD_TITLE_HINTS)

    ug = [d for d in docs if not _is_grad(d)]
    grad = [d for d in docs if _is_grad(d)]
    return ug + grad if ug else docs  # 전부 대학원뿐이면 원본 유지


def _rag_answer(
    question: str,
    llm=None,
    retriever=None,
    return_context: bool = False,
    category_hint=None,
):
    """단일 질문 RAG 파이프라인 실행.

    category_hint(data_category 문자열 또는 카테고리 집합/리스트) 주면 검색결과를
    그 카테고리(들)로 소프트 라우팅. None(기본)이면 기존 동작 그대로 — 시그니처 하위호환.
    """
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
            # use_meta_boost: 최신성+카테고리+변경키워드 소프트 가중(RRF 스케일 보정 완료) →
            # '변동/최신' 질의에서 최신 변경공지를 top-k로. query_transform 은 라이브 지연(524) 때문에 OFF.
            docs = retrieve(question, n_results=10, date_filter=date_filter, use_meta_boost=True)
        except Exception:
            docs = []
        try:
            from retrieval.reranker import rerank
            # 카테고리 힌트 있으면 rerank 전 후보를 소프트 라우팅(상위 후보 보존)
            routed = _deprioritize_grad(_soft_route_by_category(docs, category_hint))
            top_docs = rerank(question, routed, top_k=3)
        except Exception:
            routed = _deprioritize_grad(_soft_route_by_category(docs, category_hint))
            top_docs = routed[:3] if routed else []

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
        if url and url not in sources:  # 같은 URL 중복 부착 방지(출처: a, a, a → a)
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
