"""W5 Self-RAG verification: 생성된 답변이 검색 문서에 실제로 근거하는지 LLM 사후 검증.

사용 흐름 (콜랩):
  answer = generate(question, retrieved_docs)
  verdict = verify_answer(question, answer, retrieved_docs, llm_call=qwen_call)
  if not verdict["grounded"]:
      answer = REFUSAL_TEMPLATE  # 또는 escalation 한 번 더

판단 기준 (LLM에게 명시):
  - 답변의 핵심 사실(숫자/날짜/이름/금액)이 검색 문서 안에 있는가
  - 문서에 없는 정보를 새로 만들어내지는 않았는가

비용: 추론 1회 추가. T4 Qwen 3B 기준 청크 5개 + 답변 300자 → 0.5~1초.
"""
from typing import Callable, Optional

LLMCall = Callable[[str], str]

_VERIFY_PROMPT = """당신은 충남대 RAG 챗봇의 답변 검증자입니다.
아래 질문, 답변, 검색된 근거 문서 일부를 보고 답변이 근거 문서에 충실한지 판정하세요.

판정 규칙:
- 답변의 사실(날짜/금액/이름/규정/숫자)이 근거 문서 안에 있어야 GROUNDED.
- 근거에 없는 정보를 새로 만들어냈으면 NOT_GROUNDED.
- 근거가 충분치 않거나 모호하면 NOT_GROUNDED.

반드시 다음 한 줄 형식으로만 응답:
VERDICT: GROUNDED|NOT_GROUNDED  REASON: 한 줄 이유(50자 이내)

[질문]
{question}

[답변]
{answer}

[근거 문서들]
{docs}
"""


def _format_docs(retrieved_docs: list[dict], max_chars_per: int = 600, max_docs: int = 5) -> str:
    out = []
    for i, d in enumerate(retrieved_docs[:max_docs], 1):
        t = d.get("original_text") or d.get("text") or d.get("content") or ""
        out.append(f"({i}) {t[:max_chars_per]}")
    return "\n\n".join(out) if out else "(근거 없음)"


def verify_answer(question: str, answer: str, retrieved_docs: list[dict],
                  llm_call: Optional[LLMCall]) -> dict:
    """답변 근거성 판정. llm_call=None 이면 grounded=True 패스(검증 생략).

    Returns: {grounded: bool, reason: str, raw: str}
    """
    if not llm_call or not answer or not retrieved_docs:
        return {"grounded": True, "reason": "skip", "raw": ""}
    try:
        prompt = _VERIFY_PROMPT.format(
            question=question[:300],
            answer=answer[:800],
            docs=_format_docs(retrieved_docs),
        )
        resp = llm_call(prompt)
    except Exception as e:
        return {"grounded": True, "reason": f"verify_error:{e}", "raw": ""}
    raw = (resp or "").strip()
    s = raw.upper()
    if "NOT_GROUNDED" in s or "NOT GROUNDED" in s:
        # REASON 추출
        reason = "ungrounded"
        if "REASON:" in raw.upper():
            reason = raw.split(":", 2)[-1].strip()[:120]
        return {"grounded": False, "reason": reason, "raw": raw}
    if "GROUNDED" in s:
        return {"grounded": True, "reason": "ok", "raw": raw}
    # 판정 파싱 실패 — 보수적으로 not_grounded 처리하지 말고 통과 (생성 결과 보존)
    return {"grounded": True, "reason": "parse_fail", "raw": raw}
