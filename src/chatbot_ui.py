"""Gradio Blocks UI (Task2) — 심플 채팅(제미나이/클로드 스타일). 단일 컬럼 + CNU 엠블럼.

질문 → 분류기(model/, label 0~4) → data_category 소프트 라우팅 RAG/라이브크롤 → EXAONE 생성.
응답 상단에 작은 분류 뱃지(분류 흐름 가시화). 밝은 배경, 가운데 정렬, 하단 입력창만.

완전 로컬(외부 API 금지). 실행: python src/chatbot_ui.py
환경변수:
  GRADIO_SHARE=1  공개 share URL 발급(콜랩/원격 시연)
  UI_MOCK=1       무거운 모델/검색 없이 UI 디자인만 즉시 미리보기(로컬 점검용)
대상 Gradio 6.x (Chatbot 메시지 포맷 기본).
"""
import os
import sys
import time
from pathlib import Path

try:
    ROOT = Path(__file__).resolve().parent.parent
except NameError:
    ROOT = Path.cwd()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# 질문유형별 뱃지(이모지 + 색).
_CATEGORY_STYLE = {
    "졸업요건": ("🎓", "#6366f1"),
    "학교공지": ("📢", "#ef4444"),
    "학사일정": ("📅", "#f59e0b"),
    "식단": ("🍚", "#10b981"),
    "통학/셔틀": ("🚌", "#3b82f6"),
}

_EXAMPLES = [
    "오늘 학식 메뉴가 뭐예요?",
    "궁동행 셔틀 배차 간격이 어떻게 돼?",
    "컴퓨터인공지능학부 졸업하려면 뭐가 필요해?",
    "최근 학교 공지 뭐 올라왔어?",
    "수강신청 정정 기간이 언제예요?",
]

# 충남대학교 엠블럼 — 인라인 SVG(벡터). 외부 파일/네트워크 없이 self-contained.
_EMBLEM_SVG = """
<svg class="cnu-emblem" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg"
     role="img" aria-label="충남대학교 엠블럼">
  <circle cx="50" cy="50" r="48" fill="#ffffff" stroke="#0a4a9e" stroke-width="2.5"/>
  <circle cx="50" cy="50" r="41" fill="none" stroke="#0a4a9e" stroke-width="1"/>
  <defs>
    <path id="cnuTop" d="M14,50 A36,36 0 0 1 86,50"/>
    <path id="cnuBot" d="M19,50 A31,31 0 0 0 81,50"/>
  </defs>
  <text font-size="6" fill="#0a4a9e" font-weight="700" letter-spacing="0.4"
        font-family="Arial, sans-serif">
    <textPath href="#cnuTop" startOffset="50%" text-anchor="middle">CHUNGNAM NATIONAL UNIVERSITY</textPath>
  </text>
  <text font-size="9" fill="#0a4a9e" font-weight="700"
        font-family="'Malgun Gothic','Apple SD Gothic Neo',sans-serif">
    <textPath href="#cnuBot" startOffset="50%" text-anchor="middle">충남대학교</textPath>
  </text>
  <g stroke="#0a4a9e" stroke-width="4.2" stroke-linecap="round" fill="none">
    <line x1="36" y1="45" x2="64" y2="45"/>
    <line x1="50" y1="35" x2="50" y2="45"/>
    <line x1="40" y1="45" x2="40" y2="59"/>
    <line x1="50" y1="45" x2="50" y2="63"/>
    <line x1="60" y1="45" x2="60" y2="59"/>
  </g>
</svg>
"""

_HEADER_HTML = f"""
<div class="cnu-head">
  {_EMBLEM_SVG}
  <div class="cnu-title">충남대학교 캠퍼스 챗봇</div>
  <div class="cnu-tag">졸업요건 · 학교공지 · 학사일정 · 식단 · 통학/셔틀 안내</div>
</div>
"""

_EMPTY_HTML = f"""
<div class="cnu-empty">
  {_EMBLEM_SVG}
  <div class="cnu-empty-t">무엇을 도와드릴까요?</div>
  <div class="cnu-empty-s">아래에 질문을 입력해 대화를 시작해 보세요.</div>
</div>
"""

_DISCLAIMER_HTML = (
    '<div class="cnu-disc">AI 챗봇은 실수를 할 수 있습니다. 중요한 정보는 재차 확인하세요.</div>'
)

# 밝은 배경 + 가운데 정렬 + 심플(제미나이/클로드 느낌).
_CSS = """
.gradio-container{max-width:820px !important;margin:0 auto !important;background:#ffffff}
.cnu-head{text-align:center;padding:18px 0 8px}
.cnu-emblem{width:56px;height:56px}
.cnu-title{font-size:22px;font-weight:800;color:#0a4a9e;margin-top:8px;letter-spacing:-0.5px}
.cnu-tag{font-size:12px;color:#8a93a0;margin-top:3px}
.cnu-empty{text-align:center;color:#0a4a9e;padding:46px 10px}
.cnu-empty .cnu-emblem{width:84px;height:84px}
.cnu-empty-t{font-size:20px;font-weight:700;color:#374151;margin-top:14px}
.cnu-empty-s{font-size:13px;color:#9ca3af;margin-top:4px}
.cnu-disc{text-align:center;font-size:11px;color:#b6bcc6;margin-top:8px}
.cnu-badge{display:inline-block;padding:1px 9px;border-radius:11px;
  font-size:11px;font-weight:700;color:#fff;margin-bottom:5px}
footer{display:none !important}
"""


def _badge_html(label_name: str) -> str:
    if not label_name or label_name in ("미분류", "?"):
        return ""
    emoji, color = _CATEGORY_STYLE.get(label_name, ("💬", "#64748b"))
    return f'<span class="cnu-badge" style="background:{color}">{emoji} {label_name}</span>'


# UI 미리보기(mock) 백엔드 — 무거운 모델/검색 없이 UI만 즉시 확인용(UI_MOCK=1).
_MOCK_ANSWER = {
    "식단": "오늘 제2학생회관 학생식당 점심은 함박하이라이스 · 우동국물 · 배추김치입니다.",
    "통학/셔틀": "교내 순환 셔틀은 정문~제2학생회관 구간을 약 15분 간격으로 운행합니다.",
    "졸업요건": "졸업요건은 보통 총 130학점 이상 이수이며, 전공/교양 최소학점을 충족해야 합니다.",
    "학교공지": "최근 공지는 학사지원시스템(plus.cnu.ac.kr) 공지사항 게시판에서 확인할 수 있습니다.",
    "학사일정": "이번 학기 수강신청 정정 기간은 개강 첫 주에 진행됩니다.",
}


def _mock_answer(question: str, return_meta: bool = False):
    q = question or ""
    if any(k in q for k in ("학식", "식단", "메뉴", "밥")):
        name, cats = "식단", ["A_dining"]
    elif any(k in q for k in ("셔틀", "버스", "정류장", "통학")):
        name, cats = "통학/셔틀", ["A_shuttle"]
    elif any(k in q for k in ("졸업", "학점", "전공")):
        name, cats = "졸업요건", ["B_academic"]
    elif any(k in q for k in ("수강", "정정", "계절", "일정", "학기")):
        name, cats = "학사일정", ["B_academic"]
    else:
        name, cats = "학교공지", ["K_notices"]
    ans = (_MOCK_ANSWER[name]
           + "\n\n(UI 미리보기 모드 — 실제 모델/검색 미로딩)\n출처: plus.cnu.ac.kr")
    if return_meta:
        return ans, {"label": -1, "label_name": name, "categories": cats}
    return ans


def launch_app(share: "bool | None" = None):
    import gradio as gr

    if os.environ.get("UI_MOCK") == "1":
        chat_answer = _mock_answer
    else:
        from src.chat_pipeline import chat_answer

    if share is None:
        share = os.environ.get("GRADIO_SHARE", "0") == "1"

    def _user_submit(message, history):
        message = (message or "").strip()
        if not message:
            return "", history
        return "", (history or []) + [{"role": "user", "content": message}]

    def _bot_stream(history):
        if not history or history[-1]["role"] != "user":
            return
        question = history[-1]["content"]
        history = history + [{"role": "assistant", "content": "🤔 답변을 찾는 중…"}]
        yield history

        try:
            answer, meta = chat_answer(question, return_meta=True)
            badge = _badge_html(meta.get("label_name", ""))
        except Exception as e:
            answer, badge = f"오류가 발생했습니다: {e}", ""

        full = (badge + "\n\n" if badge else "") + (answer or "")
        step = 4
        for i in range(0, len(full), step):
            history[-1]["content"] = full[: i + step]
            yield history
            time.sleep(0.01)
        history[-1]["content"] = full
        yield history

    with gr.Blocks(theme=gr.themes.Soft(primary_hue="blue", neutral_hue="slate"),
                   css=_CSS, title="충남대학교 캠퍼스 챗봇") as demo:
        gr.HTML(_HEADER_HTML)

        chatbot = gr.Chatbot(height=470, show_label=False, placeholder=_EMPTY_HTML)

        with gr.Row():
            msg = gr.Textbox(placeholder="메시지를 입력하세요…", scale=9,
                             show_label=False, autofocus=True, container=False)
            send = gr.Button("전송", variant="primary", scale=1, min_width=72)

        gr.Examples(examples=_EXAMPLES, inputs=msg, label="예시 질문")
        with gr.Row():
            clear = gr.Button("새 대화", size="sm")
        gr.HTML(_DISCLAIMER_HTML)

        for trigger in (msg.submit, send.click):
            trigger(_user_submit, [msg, chatbot], [msg, chatbot], queue=False) \
                .then(_bot_stream, chatbot, chatbot)
        clear.click(lambda: [], None, chatbot, queue=False)

    demo.queue()
    demo.launch(share=share, server_name="0.0.0.0", inbrowser=not share)
    return demo


if __name__ == "__main__":
    launch_app()
