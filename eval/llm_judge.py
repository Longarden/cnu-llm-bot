# LLM-as-Judge: Gemini 2.0 Flash로 3축 점수 평가
# 축: accuracy(정확도) / relevance(관련성) / domain_compliance(도메인 준수)
# JUDGE_MOCK=1 환경변수 시 API 없이 더미 점수 반환
#
# 사용 SDK: google-genai (신규 SDK). 구버전 google-generativeai는 deprecated.
#   pip install google-genai

import os
import json
import re
import time
from typing import Dict, Optional

# GEMINI API 키는 환경변수로만 받음 (.env 또는 colab secret).
# 키 없으면 자동으로 mock 모드 폴백. 키 하드코딩 금지.
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

JUDGE_SYSTEM_PROMPT = """당신은 충남대학교 RAG 챗봇의 답변을 평가하는 전문 심사위원입니다.
주어진 질문과 답변을 보고 3개 축에서 0~5점으로 평가하고, 반드시 JSON만 반환하세요."""


def _build_judge_prompt(question: str, answer: str, expected: Optional[str]) -> str:
    expected_section = f"\n참고 정답:\n{expected}" if expected else ""
    return f"""다음 충남대 챗봇 질문-답변 쌍을 평가하세요.{expected_section}

질문: {question}

답변:
{answer}

평가 기준:
- accuracy (0~5): 답변 내용이 사실에 맞고 정확한가? (출처 기반, 추측 없음)
- relevance (0~5): 질문에 직접적으로 답하는가?
- domain_compliance (0~5): 충남대 도메인 규칙 준수 (출처 명시, 도메인 밖 질문 적절히 거절, 환각 없음)

반드시 JSON만 반환 (다른 텍스트 없음):
{{
  "accuracy": <0~5 정수>,
  "relevance": <0~5 정수>,
  "domain_compliance": <0~5 정수>,
  "reasoning": "<한 줄 평가 이유>"
}}"""


def judge(
    question: str,
    answer: str,
    expected: Optional[str] = None,
) -> Dict:
    """답변 1건 평가. JUDGE_MOCK=1 이면 더미 점수 반환."""
    if os.environ.get("JUDGE_MOCK", "0") == "1":
        return _mock_score(question, answer)

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        print("[judge] GEMINI_API_KEY 환경변수 없음 → mock 모드 폴백")
        return _mock_score(question, answer)

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        print("google-genai 미설치 → mock 반환 (pip install google-genai)")
        return _mock_score(question, answer)

    client = genai.Client(api_key=api_key)
    prompt = _build_judge_prompt(question, answer, expected)
    config = types.GenerateContentConfig(
        system_instruction=JUDGE_SYSTEM_PROMPT,
        max_output_tokens=512,
        temperature=0.0,
        response_mime_type="application/json",
    )

    # 503 UNAVAILABLE / 429 RESOURCE_EXHAUSTED 재시도 (지수 백오프)
    last_err = None
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL, contents=prompt, config=config,
            )
            raw = (response.text or "").strip()
            return _parse_score(raw)
        except Exception as e:
            last_err = e
            msg = str(e)
            if "503" in msg or "429" in msg or "UNAVAILABLE" in msg:
                time.sleep(2 ** attempt * 3)  # 3s, 6s, 12s
                continue
            break
    print(f"Judge API 오류: {last_err} → mock 반환")
    return _mock_score(question, answer)


def _parse_score(raw: str) -> Dict:
    """JSON 파싱. 실패 시 mock 반환."""
    # 코드블록 제거
    raw = re.sub(r"```json?\s*", "", raw)
    raw = re.sub(r"```", "", raw).strip()
    try:
        data = json.loads(raw)
        return {
            "accuracy": int(data.get("accuracy", 3)),
            "relevance": int(data.get("relevance", 3)),
            "domain_compliance": int(data.get("domain_compliance", 3)),
            "reasoning": data.get("reasoning", ""),
        }
    except Exception:
        # JSON 안에서 숫자만 추출 시도
        nums = re.findall(r'"(?:accuracy|relevance|domain_compliance)"\s*:\s*(\d)', raw)
        if len(nums) >= 3:
            return {
                "accuracy": int(nums[0]),
                "relevance": int(nums[1]),
                "domain_compliance": int(nums[2]),
                "reasoning": "",
            }
        return _mock_score("", "")


def _mock_score(question: str, answer: str) -> Dict:
    """도메인 밖 질문이면 낮은 점수, 나머지는 중간 점수 더미."""
    domain_outside_keywords = ["날씨", "주가", "야구", "영화", "BTS", "대통령", "레시피", "코로나"]
    is_outside = any(kw in question for kw in domain_outside_keywords)

    # 거절 답변이면 도메인 준수 점수 높게
    is_rejection = "해당 정보가 없습니다" in answer or "제공된 자료" in answer

    if is_outside and is_rejection:
        return {"accuracy": 5, "relevance": 5, "domain_compliance": 5, "reasoning": "mock: 도메인 밖 질문 적절히 거절"}
    if is_outside and not is_rejection:
        return {"accuracy": 1, "relevance": 1, "domain_compliance": 1, "reasoning": "mock: 도메인 밖 질문 거절 안 함"}

    return {"accuracy": 3, "relevance": 3, "domain_compliance": 3, "reasoning": "mock: 기본 점수"}


if __name__ == "__main__":
    # 간단 동작 테스트
    os.environ["JUDGE_MOCK"] = "1"
    result = judge(
        question="충남대 도서관 몇 시까지 해요?",
        answer="충남대학교 중앙도서관은 평일 오전 9시부터 오후 10시까지 운영합니다. 출처: library.cnu.ac.kr, 업데이트: 2026-05-01",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
