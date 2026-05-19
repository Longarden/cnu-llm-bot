"""Claude Haiku API로 원문에서 핵심 정보만 추출. DISTILL=1 env 게이트."""
import os
from typing import Any


def distill(text: str, category: str) -> str:
    """원문 텍스트에서 핵심 정보 추출. DISTILL=0이면 원문 그대로 반환."""
    if os.getenv("DISTILL", "0") != "1":
        return text

    try:
        import anthropic
        client = anthropic.Anthropic()
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"다음은 충남대학교 '{category}' 카테고리 웹페이지 텍스트입니다.\n"
                        "학생/교직원에게 유용한 핵심 정보만 간결하게 추출해주세요. "
                        "날짜, 장소, 연락처, 절차 등 구체적 정보를 우선하세요.\n\n"
                        f"원문:\n{text[:2000]}"
                    ),
                }
            ],
        )
        return msg.content[0].text
    except Exception as e:
        print(f"[distiller] API 실패: {e}, 원문 반환")
        return text


def distill_all(docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """전체 문서 리스트에 distillation 적용."""
    for doc in docs:
        doc["original_text"] = distill(
            doc.get("original_text", ""), doc.get("data_category", "")
        )
    return docs
