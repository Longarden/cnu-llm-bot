"""Gradio Blocks UI (Task2) — CNU 캠퍼스 챗봇. 좌측 카테고리 · 중앙 챗 · 우측 최근질문.

질문 → 분류기(model/, label 0~4) → data_category 소프트 라우팅 RAG/라이브크롤 → EXAONE 생성.
응답 상단에 예측 질문유형 뱃지를 달아 분류 흐름을 가시화(평가 Chat Interface 항목 대응).
타이핑 스트리밍 + 카테고리 사이드바 + 최근질문 패널 + 충남대 엠블럼(인라인 SVG, 외부파일 무의존).

완전 로컬(외부 API 금지). 실행: python src/chatbot_ui.py
환경변수 GRADIO_SHARE=1 이면 share URL 발급(코랩/원격 시연용).
대상 Gradio 6.x (Chatbot 메시지 포맷 기본, type 인자 없음).
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
_CATEGORIES = ["전체 카테고리", "졸업요건", "학교공지", "학사일정", "식단", "통학/셔틀"]

_EXAMPLES = [
    "오늘 학식 메뉴가 뭐예요?",
    "궁동행 셔틀 배차 간격이 어떻게 돼?",
    "컴퓨터인공지능학부 졸업하려면 뭐가 필요해?",
    "최근 학교 공지 뭐 올라왔어?",
    "수강신청 정정 기간이 언제예요?",
]

# 충남대학교 엠블럼 — 인라인 SVG(벡터). 외부 파일/네트워크 없이 self-contained, 확대해도 선명.
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

_BRAND_HTML = f"""
<div class="cnu-topbar">
  <div class="cnu-brand">
    {_EMBLEM_SVG}
    <div class="cnu-titles">
      <div class="cnu-logo">충남대학교 캠퍼스 챗봇</div>
      <div class="cnu-sub">CNU Campus ChatBot · AI 학내정보 안내</div>
    </div>
  </div>
  <div class="cnu-top-right"><span class="cnu-dot">●</span> 온라인</div>
</div>
"""

_SUBBAR_HTML = """
<div class="cnu-subbar">
  <b>전체 카테고리 검색</b>
  <span>질문유형을 자동 분류해 졸업요건 · 공지 · 학사일정 · 식단 · 셔틀을 안내합니다.</span>
</div>
"""

_EMPTY_HTML = f"""
<div class="cnu-empty">
  {_EMBLEM_SVG}
  <div>무엇이든 물어보세요. 하단에 질문을 입력해 대화를 시작해 보세요.</div>
</div>
"""

_DISCLAIMER_HTML = (
    '<div class="cnu-disc">AI 챗봇은 실수를 할 수 있습니다. 중요한 정보는 재차 확인하세요.</div>'
)

_CSS = """
.gradio-container{max-width:1180px !important}
.cnu-topbar{display:flex;align-items:center;justify-content:space-between;
  padding:12px 18px;border-bottom:2px solid #0a4a9e;margin-bottom:10px}
.cnu-brand{display:flex;align-items:center;gap:12px}
.cnu-emblem{width:46px;height:46px;flex:none}
.cnu-logo{font-size:19px;font-weight:800;letter-spacing:-0.5px;color:#0a4a9e}
.cnu-sub{font-size:11px;color:#6b7280;margin-top:1px}
.cnu-top-right{font-size:12px;color:#6b7280}
.cnu-dot{color:#10b981}
.cnu-subbar{padding:2px 2px 10px}
.cnu-subbar b{font-size:18px;color:#111827}
.cnu-subbar span{font-size:12px;color:#0a4a9e;margin-left:8px}
.cnu-side-title{font-size:13px;font-weight:700;color:#374151;margin:6px 0 6px;
  padding-bottom:6px;border-bottom:1px solid #eef0f3}
.cnu-empty{text-align:center;color:#0a4a9e;padding:34px 10px}
.cnu-empty .cnu-emblem{width:78px;height:78px;margin-bottom:12px}
.cnu-disc{text-align:center;font-size:11px;color:#9ca3af;margin-top:6px}
.cnu-badge{display:inline-block;padding:2px 10px;border-radius:12px;
  font-size:12px;font-weight:700;color:#fff;margin-bottom:6px}
.cnu-hist{font-size:13px;color:#4b5563;line-height:1.9}
footer{display:none !important}
"""


def _badge_html(label_name: str) -> str:
    if not label_name or label_name in ("미분류", "?"):
        return ""
    emoji, color = _CATEGORY_STYLE.get(label_name, ("💬", "#64748b"))
    return f'<span class="cnu-badge" style="background:{color}">{emoji} {label_name}</span>'


def _render_history(history) -> str:
    """우측 패널: 이번 세션의 최근 사용자 질문 목록(최신 위)."""
    qs = [m["content"] for m in (history or []) if m.get("role") == "user"]
    if not qs:
        return "<div class='cnu-hist'>아직 질문이 없습니다.</div>"
    items = "".join(f"• {q}<br>" for q in reversed(qs[-8:]))
    return f"<div class='cnu-hist'>{items}</div>"


def launch_app(share: "bool | None" = None):
    import gradio as gr
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

    with gr.Blocks(theme=gr.themes.Soft(primary_hue="blue"), css=_CSS,
                   title="충남대학교 캠퍼스 챗봇") as demo:
        gr.HTML(_BRAND_HTML)

        with gr.Row():
            # 좌측: 카테고리 사이드바
            with gr.Column(scale=2, min_width=160):
                gr.HTML("<div class='cnu-side-title'>카테고리</div>")
                gr.Radio(_CATEGORIES, value="전체 카테고리", show_label=False,
                         container=False)

            # 중앙: 챗
            with gr.Column(scale=7):
                gr.HTML(_SUBBAR_HTML)
                chatbot = gr.Chatbot(height=430, show_label=False,
                                     placeholder=_EMPTY_HTML)
                with gr.Row():
                    msg = gr.Textbox(placeholder="메시지를 작성하세요.", scale=9,
                                     show_label=False, autofocus=True, container=False)
                    send = gr.Button("전송", variant="primary", scale=1, min_width=70)
                gr.Examples(examples=_EXAMPLES, inputs=msg, label="예시 질문")
                gr.HTML(_DISCLAIMER_HTML)
                clear = gr.Button("대화 초기화", size="sm")

            # 우측: 최근 질문
            with gr.Column(scale=2, min_width=160):
                gr.HTML("<div class='cnu-side-title'>최근 질문</div>")
                history_md = gr.HTML("<div class='cnu-hist'>아직 질문이 없습니다.</div>")

        for trigger in (msg.submit, send.click):
            trigger(_user_submit, [msg, chatbot], [msg, chatbot], queue=False) \
                .then(_bot_stream, chatbot, chatbot) \
                .then(_render_history, chatbot, history_md)
        clear.click(lambda: ([], "<div class='cnu-hist'>아직 질문이 없습니다.</div>"),
                    None, [chatbot, history_md], queue=False)

    demo.queue()
    demo.launch(share=share, server_name="0.0.0.0")
    return demo


if __name__ == "__main__":
    launch_app()
