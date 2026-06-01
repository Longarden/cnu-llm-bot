"""Gradio ChatInterface UI (Task2). 분류 라우팅 포함 응답.

app/gradio_app.py 의 ChatInterface 패턴을 재사용/확장:
질문 → 분류기(model/, label 0~4) → data_category 소프트 라우팅 RAG → EXAONE 생성.
응답 헤더에 예측된 질문유형/카테고리를 표시(분류 흐름 가시화, 평가 Chat Interface 항목 대응).

완전 로컬(외부 API 금지). 실행: python src/chatbot_ui.py
환경변수 GRADIO_SHARE=1 이면 share URL 발급(코랩/원격 시연용).
"""
import os
import sys
from pathlib import Path

try:
    ROOT = Path(__file__).resolve().parent.parent
except NameError:
    ROOT = Path.cwd()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def launch_app(share: bool | None = None):
    import gradio as gr
    from src.chat_pipeline import chat_answer

    if share is None:
        share = os.environ.get("GRADIO_SHARE", "0") == "1"

    def chat(message: str, history: list) -> str:
        try:
            answer, meta = chat_answer(message, return_meta=True)
            # 분류 흐름 가시화: 예측 유형/카테고리 헤더
            cats = ", ".join(meta.get("categories") or []) or "전체검색"
            header = f"[질문유형: {meta['label_name']} → {cats}]"
            return f"{header}\n\n{answer}"
        except Exception as e:
            return f"오류가 발생했습니다: {e}"

    demo = gr.ChatInterface(
        fn=chat,
        title="충남대학교 캠퍼스 챗봇",
        description="질문을 입력하면 질문유형을 자동 분류해 졸업요건·공지·학사일정·식단·셔틀 정보를 안내합니다.",
        examples=[
            "오늘 학식 메뉴가 뭐예요?",
            "궁동행 셔틀 배차 간격이 어떻게 돼?",
            "컴퓨터인공지능학부 졸업하려면 뭐가 필요해?",
            "최근 학교 공지 뭐 올라왔어?",
            "수강신청 정정 기간이 언제예요?",
        ],
        theme=gr.themes.Soft(),
    )
    demo.launch(share=share, server_name="0.0.0.0")
    return demo


if __name__ == "__main__":
    launch_app()
