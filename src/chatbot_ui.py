"""Gradio Blocks UI (Task2) — 심플 채팅(클로드/제미나이 스타일). 흰 배경, 단일 컬럼.

질문 → 분류기(model/, label 0~4) → data_category 소프트 라우팅 RAG/라이브크롤 → EXAONE 생성.
응답 상단에 작은 분류 뱃지. 테두리/그림자 없는 깔끔한 흰 화면 + 하단 입력창만.

완전 로컬(외부 API 금지). 실행: python src/chatbot_ui.py
환경변수:
  GRADIO_SHARE=1  공개 share URL 발급(콜랩/원격 시연)
  UI_MOCK=1       무거운 모델/검색 없이 UI 디자인만 즉시 미리보기(로컬 점검)
대상 Gradio 6.x.
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

_CATEGORY_STYLE = {
    "졸업요건": ("🎓", "#6366f1"),
    "학교공지": ("📢", "#ef4444"),
    "학사일정": ("📅", "#f59e0b"),
    "식단": ("🍚", "#10b981"),
    "통학/셔틀": ("🚌", "#3b82f6"),
}

# 충남대학교 엠블럼 — 인라인 SVG(벡터, 외부파일/네트워크 무의존).
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
</div>
"""

_EMPTY_HTML = f"""
<div class="cnu-empty">
  {_EMBLEM_SVG}
  <div class="cnu-empty-t">무엇을 도와드릴까요?</div>
</div>
"""

# 깔끔담백 흰 배경 + 테두리/그림자 제거(블록 구분선 없이 이어지게).
_CSS = """
/* 라이트모드 강제 */
:root, .dark {
  --body-background-fill:#ffffff !important;
  --background-fill-primary:#ffffff !important;
  --background-fill-secondary:#f9f9fb !important;
  --block-background-fill:#ffffff !important;
  --block-border-color:transparent !important;
  --border-color-primary:#e8e9ed !important;
  --body-text-color:#111827 !important;
  --body-text-color-subdued:#6b7280 !important;
  --input-background-fill:#ffffff !important;
  --button-primary-background-fill:#0a4a9e !important;
  --button-primary-text-color:#ffffff !important;
  color-scheme: light !important;
}
body, gradio-app {
  background:#ffffff !important;
  font-family:'Malgun Gothic','Apple SD Gothic Neo','Noto Sans KR',sans-serif !important;
}
.gradio-container {
  max-width:1320px !important; margin:0 auto !important;
  background:#ffffff !important; padding:0 32px 40px !important;
}
.block, .form, .panel { border:none !important; box-shadow:none !important; background:#ffffff !important; }
/* 내부 래퍼 폭 제한 해제 → 가로 여백 채우기(컨테이너 폭까지 가득) */
.gradio-container .main, .gradio-container .wrap, .gradio-container .contain,
.gradio-container .fillable, .gradio-container .app, .gradio-container > div {
  max-width:100% !important; width:100% !important;
}
.cnu-chat, .cnu-inputrow, .cnu-chat .bubble-wrap ~ * { width:100% !important; max-width:100% !important; }
.cnu-chat { min-height:520px !important; }

/* 헤더 */
.cnu-head { text-align:center; padding:32px 0 10px; border-bottom:1px solid #f0f1f4; }
.cnu-emblem { width:50px; height:50px; display:block; margin:0 auto; }
.cnu-title { font-size:19px; font-weight:700; color:#0a4a9e; margin-top:10px; letter-spacing:-0.3px; line-height:1.3; }

/* 챗 영역 */
.cnu-chat { background:#ffffff !important; border:none !important; box-shadow:none !important; padding:8px 0 !important; }
.cnu-chat .message-wrap, .cnu-chat [class*="message-wrap"] { padding:0 !important; gap:0 !important; }

/* 유저 메시지 — 오른쪽, CNU 블루 */
.cnu-chat .user, .cnu-chat [data-testid="user"], .cnu-chat .message.user {
  display:flex !important; justify-content:flex-end !important; margin:10px 0 !important; padding:0 4px !important;
}
.cnu-chat .user .bubble-wrap, .cnu-chat [data-testid="user"] .bubble-wrap, .cnu-chat .message.user .bubble-wrap {
  background:#0a4a9e !important; color:#ffffff !important; border-radius:18px 18px 4px 18px !important;
  padding:10px 16px !important; max-width:72% !important; font-size:14.5px !important; line-height:1.6 !important;
  box-shadow:0 1px 4px rgba(10,74,158,.15) !important;
}

/* 봇 메시지 — 왼쪽, 연회색 */
.cnu-chat .bot, .cnu-chat [data-testid="bot"], .cnu-chat .message.bot {
  display:flex !important; justify-content:flex-start !important; margin:10px 0 !important; padding:0 4px !important;
}
.cnu-chat .bot .bubble-wrap, .cnu-chat [data-testid="bot"] .bubble-wrap, .cnu-chat .message.bot .bubble-wrap {
  background:#f4f5f8 !important; color:#111827 !important; border-radius:18px 18px 18px 4px !important;
  padding:12px 18px !important; max-width:78% !important; font-size:14.5px !important; line-height:1.7 !important;
  box-shadow:none !important; border:1px solid #ecedf1 !important;
}
.cnu-chat .avatar-container, .cnu-chat [class*="avatar"] { display:none !important; }
.cnu-chat .bubble-wrap p { margin:0 0 6px !important; }
.cnu-chat .bubble-wrap p:last-child { margin-bottom:0 !important; }
.cnu-chat .bubble-wrap a { color:#0a4a9e; text-decoration:underline; text-underline-offset:2px; }
.cnu-chat .user .bubble-wrap a { color:#cfe0ff; }
.cnu-chat .bubble-wrap code { background:rgba(0,0,0,.06); border-radius:4px; padding:1px 5px; font-size:13px; }

/* 빈 화면 */
.cnu-empty { text-align:center; padding:72px 10px 56px; display:flex; flex-direction:column; align-items:center; }
.cnu-empty .cnu-emblem { width:80px; height:80px; margin:0 auto 18px; opacity:.9; }
.cnu-empty-t { font-size:20px; font-weight:600; color:#374151; letter-spacing:-0.2px; line-height:1.4; }

/* 입력 바 — 알약형 + 포커스 링 */
.cnu-inputrow {
  display:flex !important; align-items:center !important; background:#ffffff !important;
  border:1.5px solid #dde0e8 !important; border-radius:26px !important;
  padding:6px 6px 6px 18px !important; margin-top:14px !important;
  box-shadow:0 2px 8px rgba(0,0,0,.055) !important; transition:border-color .18s ease, box-shadow .18s ease !important;
}
.cnu-inputrow:focus-within {
  border-color:#0a4a9e !important; box-shadow:0 0 0 3px rgba(10,74,158,.10), 0 2px 8px rgba(0,0,0,.055) !important;
}
.cnu-inputrow textarea, .cnu-inputrow input[type="text"] {
  border:none !important; outline:none !important; box-shadow:none !important; background:transparent !important;
  font-size:15px !important; line-height:1.55 !important; color:#111827 !important; resize:none !important;
  padding:4px 0 !important; min-height:38px !important; font-family:inherit !important;
}
.cnu-inputrow textarea::placeholder, .cnu-inputrow input[type="text"]::placeholder { color:#9ca3af !important; }
.cnu-inputrow button[variant="primary"], .cnu-inputrow .btn-primary, .cnu-inputrow button.primary {
  background:#0a4a9e !important; color:#ffffff !important; border:none !important; border-radius:20px !important;
  padding:8px 20px !important; font-size:14px !important; font-weight:600 !important; font-family:inherit !important;
  cursor:pointer !important; flex-shrink:0 !important; box-shadow:none !important; white-space:nowrap !important;
  transition:background .16s ease, transform .12s ease !important;
}
.cnu-inputrow button[variant="primary"]:hover, .cnu-inputrow .btn-primary:hover, .cnu-inputrow button.primary:hover {
  background:#083d88 !important; transform:translateY(-1px) !important;
}
.cnu-inputrow button[variant="primary"]:active, .cnu-inputrow .btn-primary:active, .cnu-inputrow button.primary:active {
  transform:translateY(0) !important; background:#072f6a !important;
}

/* 분류 뱃지 */
.cnu-badge {
  display:inline-block; padding:2px 10px; border-radius:12px; font-size:11.5px; font-weight:700;
  color:#ffffff; margin-bottom:7px; letter-spacing:.2px;
}

/* 기타 정리 */
footer { display:none !important; }
.cnu-chat label, .cnu-chat .label-wrap { display:none !important; }
.cnu-chat ::-webkit-scrollbar { width:5px; }
.cnu-chat ::-webkit-scrollbar-track { background:transparent; }
.cnu-chat ::-webkit-scrollbar-thumb { background:#dde0e8; border-radius:10px; }
.cnu-chat ::-webkit-scrollbar-thumb:hover { background:#c4c8d4; }
.cnu-chat .message { animation:msgIn .22s cubic-bezier(.25,.8,.25,1) both; }
@keyframes msgIn { from { opacity:0; transform:translateY(6px); } to { opacity:1; transform:translateY(0); } }
"""


def _badge_html(label_name: str) -> str:
    if not label_name or label_name in ("미분류", "?"):
        return ""
    emoji, color = _CATEGORY_STYLE.get(label_name, ("💬", "#64748b"))
    return f'<span class="cnu-badge" style="background:{color}">{emoji} {label_name}</span>'


# UI 미리보기(mock) 백엔드 — 무거운 모델/검색 없이 UI만 즉시 확인(UI_MOCK=1).
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
           + "\n\n(UI 미리보기 모드 — 실제 모델/검색 미로딩)")
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

        chatbot = gr.Chatbot(height=500, show_label=False, placeholder=_EMPTY_HTML,
                             elem_classes="cnu-chat")

        with gr.Row(elem_classes="cnu-inputrow"):
            msg = gr.Textbox(placeholder="메시지를 입력하세요…", scale=9,
                             show_label=False, autofocus=True, container=False)
            send = gr.Button("전송", variant="primary", scale=1, min_width=72)

        for trigger in (msg.submit, send.click):
            trigger(_user_submit, [msg, chatbot], [msg, chatbot], queue=False) \
                .then(_bot_stream, chatbot, chatbot)

    demo.queue()
    demo.launch(share=share, server_name="0.0.0.0", inbrowser=not share)
    return demo


if __name__ == "__main__":
    launch_app()
