"""
FastAPI 서버 (과제 슬라이드 6 "Working API" 요구사항).

사람용 화면(Gradio)과 별개로, 프로그램이 질문을 Request로 보내면
답을 Response(JSON)로 돌려주는 서버 엔드포인트.

내부적으로는 Gradio와 동일한 interface._rag_answer 를 그대로 호출한다.
(생성 모델 = 로컬 Qwen2.5-7B-AWQ, OOM 시 3B 폴백)

실행:
    uvicorn app.api_server:app --host 0.0.0.0 --port 8000
또는:
    python -m app.api_server

호출 예시:
    curl -X POST http://localhost:8000/ask \
         -H "Content-Type: application/json" \
         -d '{"question": "도서관 열람실 몇 시까지 해요?"}'
"""

import threading
import time
from typing import List

from fastapi import FastAPI
from pydantic import BaseModel

from interface.answer_questions import _rag_answer


app = FastAPI(
    title="충남대학교 학내정보 Q/A API",
    description="RAG 기반 학내정보 챗봇 API (벡터DB 검색 + 로컬 EXAONE 생성).",
    version="1.0.0",
)

# 단일 GPU에서 동시 요청이 생성기에 같이 들어가면 메모리 경합/OOM → 직렬화.
_gen_lock = threading.Lock()


@app.on_event("startup")
def _warmup() -> None:
    """서버 기동 시 모델·인덱스를 미리 로드(첫 HTTP 요청의 콜드스타트 제거).

    UI(chatbot_ui)는 이미 워밍업하지만 API 서버에는 없어 첫 /ask 가 모델 3종+BM25
    인덱스를 통째로 로드하느라 수 분 걸렸음. 더미 질문 1건으로 전 경로를 데워둔다.
    """
    try:
        print("[api] 워밍업 중(모델/인덱스 선로딩)…")
        _rag_answer("워밍업", return_context=True)
        print("[api] 워밍업 완료 — 첫 요청부터 빠르게 응답")
    except Exception as e:
        print(f"[api] 워밍업 건너뜀(첫 요청 때 로드): {e}")


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    question: str
    answer: str
    sources: List[str]
    rejected: bool
    latency_ms: int


@app.get("/")
def health() -> dict:
    """헬스 체크. 서버가 살아있는지 확인용."""
    return {"status": "ok", "service": "cnu-llm-bot Q/A API"}


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest) -> AskResponse:
    """질문 1건을 받아 RAG 파이프라인으로 답변을 생성해 반환."""
    start = time.perf_counter()
    with _gen_lock:  # 생성은 단일 GPU 직렬 — 동시요청 경합/OOM 방지
        answer, top_docs, rejected = _rag_answer(req.question, return_context=True)
    elapsed_ms = round((time.perf_counter() - start) * 1000)

    # 출처 URL 추출 (중복 제거, gradio_app / answer_questions 와 동일 규칙)
    sources: List[str] = []
    for d in top_docs:
        meta = d.get("metadata", d)
        url = meta.get("source_url", "")
        if url and url not in sources:
            sources.append(url)

    return AskResponse(
        question=req.question,
        answer=answer,
        sources=sources,
        rejected=rejected,
        latency_ms=elapsed_ms,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
