"""W2 쿼리 변환: HyDE + Multi-Query.

- expand_multi_query: 원 질문 → 다른 표현 N개 (sparse recall ↑)
- hyde: 원 질문 → 가상 답변 1문장 (dense recall ↑)
- llm_call: Callable[[str], str]. 콜랩에서 Qwen 추론기 주입. 없으면 노옵.

설계 의도: hybrid_retriever 외부에서 LLM 의존 격리. 코드 변경 최소.
"""
from typing import Callable, Optional

LLMCall = Callable[[str], str]


_MQ_PROMPT = """다음 충남대 챗봇 질문을 의미는 같지만 다른 표현으로 {n}개 만들어주세요.
각 표현은 한 줄씩, 번호나 부호 없이 질문 문장만 출력하세요.

원 질문: {q}

다른 표현:"""

_HYDE_PROMPT = """다음은 충남대 챗봇에 들어온 질문입니다. 만약 이 질문에 답한다면
어떤 정보가 들어 있을지 1~2문장의 가상 답변을 작성하세요.
실제 사실을 모르면 "충남대학교 ..." 처럼 일반적 형식으로 작성하세요.

질문: {q}

가상 답변:"""


def expand_multi_query(question: str, llm_call: Optional[LLMCall], n: int = 2) -> list[str]:
    """원 질문 + 변형 n개. llm_call=None 이면 원 질문만 반환."""
    base = [question]
    if not llm_call:
        return base
    try:
        resp = llm_call(_MQ_PROMPT.format(n=n, q=question))
    except Exception:
        return base
    if not resp:
        return base
    variants = []
    for line in resp.splitlines():
        s = line.strip().lstrip("-*0123456789.) ").strip()
        if not s or s == question or s in base + variants:
            continue
        # 너무 짧거나 긴 변형은 신뢰 X
        if 5 <= len(s) <= 200:
            variants.append(s)
        if len(variants) >= n:
            break
    return base + variants


def hyde(question: str, llm_call: Optional[LLMCall]) -> Optional[str]:
    """가상 답변 1~2문장. llm_call=None 이면 None."""
    if not llm_call:
        return None
    try:
        resp = llm_call(_HYDE_PROMPT.format(q=question))
    except Exception:
        return None
    if not resp:
        return None
    text = resp.strip()
    # 너무 짧으면 노이즈, 너무 길면 자른다
    if len(text) < 10:
        return None
    return text[:400]
