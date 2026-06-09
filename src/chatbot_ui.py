"""커스텀 웹 챗봇 UI (Task2) — FastAPI + 단일 HTML(클로드/제미나이 스타일). Gradio 미사용.

질문 → 분류기(model/, label 0~4) → data_category 소프트 라우팅 RAG/라이브크롤 → EXAONE 생성.
FastAPI가 직접 만든 단일 페이지(HTML/CSS/JS, 외부 의존 0)를 서빙하고 POST /api/chat 으로 응답.
대화흐름/질문입력/응답출력 + 카테고리 뱃지 + 타자효과. 과제 Task2 정성평가(UI/형식/맥락) 충족.

완전 로컬(외부 API 금지). 실행: python src/chatbot_ui.py
환경변수:
  GRADIO_SHARE=1 (또는 SHARE=1)  cloudflared 퀵터널로 공개 링크 발급(콜랩/원격 시연, 토큰 불필요)
  UI_MOCK=1                       무거운 모델/검색 없이 UI만 즉시 미리보기(로컬 점검)
  PORT (기본 7860)                서버 포트
chatbot.sh 의 마지막 `python src/chatbot_ui.py` 가 이 서버를 띄운다(기존 호출 그대로).
"""
import os
import re
import sys
import stat
import time
import socket
import shutil
import threading
import subprocess
import webbrowser
import urllib.request
from pathlib import Path

try:
    ROOT = Path(__file__).resolve().parent.parent
except NameError:
    ROOT = Path.cwd()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ── 충남대학교 엠블럼 (인라인 SVG, 외부파일/네트워크 무의존) ─────────────
_EMBLEM_SVG = """
<svg class="cnu-emblem" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="충남대학교 엠블럼">
  <circle cx="50" cy="50" r="48" fill="#ffffff" stroke="#0a4a9e" stroke-width="2.5"/>
  <circle cx="50" cy="50" r="41" fill="none" stroke="#0a4a9e" stroke-width="1"/>
  <defs><path id="cnuTop" d="M14,50 A36,36 0 0 1 86,50"/><path id="cnuBot" d="M19,50 A31,31 0 0 0 81,50"/></defs>
  <text font-size="6" fill="#0a4a9e" font-weight="700" letter-spacing="0.4" font-family="Arial,sans-serif"><textPath href="#cnuTop" startOffset="50%" text-anchor="middle">CHUNGNAM NATIONAL UNIVERSITY</textPath></text>
  <text font-size="9" fill="#0a4a9e" font-weight="700" font-family="'Malgun Gothic','Apple SD Gothic Neo',sans-serif"><textPath href="#cnuBot" startOffset="50%" text-anchor="middle">충남대학교</textPath></text>
  <g stroke="#0a4a9e" stroke-width="4.2" stroke-linecap="round" fill="none">
    <line x1="36" y1="45" x2="64" y2="45"/><line x1="50" y1="35" x2="50" y2="45"/><line x1="40" y1="45" x2="40" y2="59"/><line x1="50" y1="45" x2="50" y2="63"/><line x1="60" y1="45" x2="60" y2="59"/>
  </g>
</svg>
"""

# ── 단일 페이지(HTML/CSS/JS). raw 문자열로 JS의 \n 등 백슬래시 보존. {{EMBLEM}} 치환. ──
_INDEX_HTML = r"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>충남대학교 캠퍼스 챗봇</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  :root {
    --cnu-blue: #0a4a9e; --cnu-blue-light: #1a5ab5; --cnu-blue-dim: rgba(10,74,158,0.08);
    --bg: #ffffff; --surface: #f7f8fa; --border: #e5e7eb; --text: #1a1a2e; --text-muted: #6b7280;
    --bubble-user-bg: var(--cnu-blue); --bubble-user-text: #fff; --bubble-ai-bg: #f1f3f5; --bubble-ai-text: #1a1a2e;
    --input-bg: #fff; --shadow-sm: 0 1px 3px rgba(0,0,0,0.08); --shadow-md: 0 4px 16px rgba(0,0,0,0.10);
    --radius-msg: 18px; --max-width: 1080px;
    --font: 'Apple SD Gothic Neo','Malgun Gothic','Noto Sans KR',sans-serif;
  }
  html, body { height: 100%; font-family: var(--font); background: var(--bg); color: var(--text); -webkit-font-smoothing: antialiased; }
  body { display: flex; flex-direction: column; height: 100vh; overflow: hidden; }
  .header { flex-shrink: 0; background: var(--bg); border-bottom: 1px solid var(--border); padding: 0 24px; height: 62px; display: flex; align-items: center; box-shadow: var(--shadow-sm); z-index: 10; }
  .header-inner { width: 100%; max-width: var(--max-width); margin: 0 auto; display: flex; align-items: center; gap: 12px; }
  .cnu-emblem { flex-shrink: 0; }
  .header .cnu-emblem { width: 46px; height: 46px; }
  .header-title { display: flex; flex-direction: column; gap: 1px; }
  .header-title .main { font-size: 17px; font-weight: 700; color: var(--cnu-blue); letter-spacing: -0.3px; line-height: 1.2; }
  .header-title .sub { font-size: 11.5px; color: var(--text-muted); letter-spacing: 0.02em; }
  .header-badge { margin-left: auto; background: var(--cnu-blue-dim); color: var(--cnu-blue); font-size: 11.5px; font-weight: 600; padding: 4px 10px; border-radius: 20px; }
  .chat-wrap { flex: 1; overflow-y: auto; overflow-x: hidden; padding: 0 24px; scroll-behavior: smooth; }
  .chat-inner { width: 100%; max-width: var(--max-width); margin: 0 auto; padding: 28px 0 16px; display: flex; flex-direction: column; gap: 4px; min-height: 100%; }
  .empty-state { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 20px; padding: 60px 0; animation: fadeIn 0.4s ease; }
  .empty-state .cnu-emblem { width: 84px; height: 84px; opacity: 0.85; }
  .empty-state-text { font-size: 22px; font-weight: 600; color: var(--text); letter-spacing: -0.4px; }
  .empty-state-sub { font-size: 14px; color: var(--text-muted); text-align: center; line-height: 1.7; margin-top: -8px; }
  .quick-chips { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; margin-top: 4px; }
  .chip { background: var(--surface); border: 1.5px solid var(--border); color: var(--text); font-size: 13px; padding: 8px 16px; border-radius: 20px; cursor: pointer; transition: all 0.15s ease; font-family: var(--font); font-weight: 500; }
  .chip:hover { background: var(--cnu-blue-dim); border-color: var(--cnu-blue); color: var(--cnu-blue); transform: translateY(-1px); }
  .msg-row { display: flex; gap: 8px; max-width: 100%; animation: slideIn 0.22s ease; }
  .msg-row.user { justify-content: flex-end; margin-left: auto; padding-left: 80px; }
  .msg-row.ai { justify-content: flex-start; padding-right: 80px; }
  .msg-group { display: flex; flex-direction: column; gap: 3px; max-width: 100%; }
  .msg-row.user .msg-group { align-items: flex-end; }
  .msg-row.ai .msg-group { align-items: flex-start; }
  .category-badge { display: inline-flex; align-items: center; gap: 4px; font-size: 11.5px; font-weight: 600; padding: 3px 9px; border-radius: 12px; margin-bottom: 2px; }
  .bubble { padding: 12px 16px; border-radius: var(--radius-msg); font-size: 15px; line-height: 1.65; word-break: break-word; white-space: pre-wrap; max-width: 760px; box-shadow: var(--shadow-sm); }
  .msg-row.user .bubble { background: var(--bubble-user-bg); color: var(--bubble-user-text); border-bottom-right-radius: 5px; }
  .msg-row.ai .bubble { background: var(--bubble-ai-bg); color: var(--bubble-ai-text); border-bottom-left-radius: 5px; }
  .bubble.error { background: #fff1f2; color: #be123c; border: 1px solid #fda4af; }
  .thinking { display: flex; align-items: center; gap: 6px; padding: 13px 18px; background: var(--bubble-ai-bg); border-radius: var(--radius-msg); border-bottom-left-radius: 5px; width: fit-content; box-shadow: var(--shadow-sm); }
  .dot { width: 7px; height: 7px; border-radius: 50%; background: #9ca3af; animation: bounce 1.2s ease-in-out infinite; }
  .dot:nth-child(2) { animation-delay: 0.2s; } .dot:nth-child(3) { animation-delay: 0.4s; }
  .timestamp { font-size: 10.5px; color: var(--text-muted); padding: 0 2px; }
  .msg-spacer { height: 10px; }
  .bottom-bar { flex-shrink: 0; background: var(--bg); border-top: 1px solid var(--border); padding: 14px 24px 12px; z-index: 10; }
  .bottom-inner { width: 100%; max-width: var(--max-width); margin: 0 auto; display: flex; flex-direction: column; gap: 8px; }
  .input-pill { display: flex; align-items: flex-end; gap: 10px; background: var(--input-bg); border: 1.5px solid var(--border); border-radius: 26px; padding: 10px 14px 10px 20px; box-shadow: var(--shadow-md); transition: border-color 0.15s ease, box-shadow 0.15s ease; }
  .input-pill:focus-within { border-color: var(--cnu-blue); box-shadow: 0 0 0 3px rgba(10,74,158,0.10), var(--shadow-md); }
  #inp { flex: 1; border: none; outline: none; background: transparent; font-family: var(--font); font-size: 15px; color: var(--text); resize: none; line-height: 1.6; max-height: 160px; min-height: 24px; overflow-y: auto; padding: 2px 0; }
  #inp::placeholder { color: #b0b7c3; }
  #send { flex-shrink: 0; background: var(--cnu-blue); color: #fff; border: none; border-radius: 20px; font-family: var(--font); font-size: 14px; font-weight: 600; padding: 8px 18px; cursor: pointer; transition: background 0.15s ease, transform 0.1s ease; align-self: flex-end; min-width: 60px; line-height: 1.4; }
  #send:hover:not(:disabled) { background: var(--cnu-blue-light); transform: translateY(-1px); }
  #send:disabled { background: #c4cfe0; cursor: not-allowed; }
  .disclaimer { font-size: 11.5px; color: var(--text-muted); text-align: center; }
  .chat-wrap::-webkit-scrollbar { width: 6px; }
  .chat-wrap::-webkit-scrollbar-track { background: transparent; }
  .chat-wrap::-webkit-scrollbar-thumb { background: #d1d5db; border-radius: 3px; }
  .chat-wrap::-webkit-scrollbar-thumb:hover { background: #9ca3af; }
  @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
  @keyframes slideIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
  @keyframes bounce { 0%,80%,100% { transform: translateY(0); } 40% { transform: translateY(-6px); } }
  @media (max-width: 720px) {
    .header { padding: 0 14px; height: 56px; } .chat-wrap { padding: 0 12px; } .bottom-bar { padding: 12px 12px 10px; }
    .msg-row.user { padding-left: 40px; } .msg-row.ai { padding-right: 40px; } .bubble { font-size: 14px; }
    .header-title .main { font-size: 15px; } .header-badge { display: none; }
  }
</style>
</head>
<body>
<header class="header">
  <div class="header-inner">
    {{EMBLEM}}
    <div class="header-title">
      <span class="main">충남대학교 캠퍼스 챗봇</span>
      <span class="sub">Chungnam National University AI Assistant</span>
    </div>
    <span class="header-badge">Beta</span>
  </div>
</header>
<div class="chat-wrap" id="chatWrap">
  <div class="chat-inner" id="chatInner">
    <div class="empty-state" id="emptyState">
      {{EMBLEM}}
      <div class="empty-state-text">무엇을 도와드릴까요?</div>
      <div class="empty-state-sub">학사일정, 식단, 셔틀버스, 학교공지 등<br>궁금한 것을 편하게 질문해 보세요.</div>
      <div class="quick-chips">
        <button class="chip" data-q="오늘 식단 알려줘">🍚 오늘 식단</button>
        <button class="chip" data-q="이번 주 학사일정 알려줘">📅 학사일정</button>
        <button class="chip" data-q="셔틀버스 시간표 알려줘">🚌 셔틀버스</button>
        <button class="chip" data-q="최근 학교 공지사항 알려줘">📢 학교공지</button>
        <button class="chip" data-q="졸업 요건 알려줘">🎓 졸업요건</button>
      </div>
    </div>
  </div>
</div>
<div class="bottom-bar">
  <div class="bottom-inner">
    <div class="input-pill">
      <textarea id="inp" rows="1" placeholder="메시지를 입력하세요…" autocomplete="off" autocorrect="off" spellcheck="false"></textarea>
      <button id="send">전송</button>
    </div>
    <div class="disclaimer">AI 챗봇은 실수를 할 수 있습니다. 중요한 정보는 재차 확인하세요.</div>
  </div>
</div>
<script>
(function () {
  'use strict';
  const CATEGORIES = {
    '졸업요건':  { emoji: '🎓', color: '#6366f1', bg: 'rgba(99,102,241,0.10)' },
    '학교공지':  { emoji: '📢', color: '#ef4444', bg: 'rgba(239,68,68,0.10)' },
    '학사일정':  { emoji: '📅', color: '#f59e0b', bg: 'rgba(245,158,11,0.10)' },
    '식단':      { emoji: '🍚', color: '#10b981', bg: 'rgba(16,185,129,0.10)' },
    '통학/셔틀': { emoji: '🚌', color: '#3b82f6', bg: 'rgba(59,130,246,0.10)' },
  };
  let isBusy = false, thinkingEl = null;
  const chatInner = document.getElementById('chatInner');
  const chatWrap = document.getElementById('chatWrap');
  const emptyState = document.getElementById('emptyState');
  const inp = document.getElementById('inp');
  const sendBtn = document.getElementById('send');
  function scrollToBottom() { chatWrap.scrollTo({ top: chatWrap.scrollHeight, behavior: 'smooth' }); }
  function getTime() { const n = new Date(); return String(n.getHours()).padStart(2,'0') + ':' + String(n.getMinutes()).padStart(2,'0'); }
  function removeEmptyState() { if (emptyState && emptyState.parentNode) emptyState.parentNode.removeChild(emptyState); }
  function resizeInp() { inp.style.height = 'auto'; inp.style.height = Math.min(inp.scrollHeight, 160) + 'px'; }
  inp.addEventListener('input', resizeInp);
  function appendUserBubble(text) {
    const row = document.createElement('div'); row.className = 'msg-row user';
    const group = document.createElement('div'); group.className = 'msg-group';
    const bubble = document.createElement('div'); bubble.className = 'bubble'; bubble.textContent = text;
    const ts = document.createElement('div'); ts.className = 'timestamp'; ts.textContent = getTime();
    group.appendChild(bubble); group.appendChild(ts); row.appendChild(group); chatInner.appendChild(row);
    const sp = document.createElement('div'); sp.className = 'msg-spacer'; chatInner.appendChild(sp); scrollToBottom();
  }
  function showThinking() {
    const row = document.createElement('div'); row.className = 'msg-row ai';
    const group = document.createElement('div'); group.className = 'msg-group';
    const t = document.createElement('div'); t.className = 'thinking';
    t.innerHTML = '<div class="dot"></div><div class="dot"></div><div class="dot"></div>';
    group.appendChild(t); row.appendChild(group); chatInner.appendChild(row); thinkingEl = row; scrollToBottom();
  }
  function removeThinking() { if (thinkingEl && thinkingEl.parentNode) { thinkingEl.parentNode.removeChild(thinkingEl); thinkingEl = null; } }
  function appendAiBubble(text, label, isError) {
    const row = document.createElement('div'); row.className = 'msg-row ai';
    const group = document.createElement('div'); group.className = 'msg-group';
    if (label && CATEGORIES[label] && !isError) {
      const cat = CATEGORIES[label]; const badge = document.createElement('div');
      badge.className = 'category-badge'; badge.style.color = cat.color; badge.style.background = cat.bg;
      badge.textContent = cat.emoji + ' ' + label; group.appendChild(badge);
    }
    const bubble = document.createElement('div'); bubble.className = isError ? 'bubble error' : 'bubble';
    const ts = document.createElement('div'); ts.className = 'timestamp'; ts.textContent = getTime();
    group.appendChild(bubble); group.appendChild(ts); row.appendChild(group); chatInner.appendChild(row);
    const sp = document.createElement('div'); sp.className = 'msg-spacer'; chatInner.appendChild(sp);
    if (isError) { bubble.textContent = text; scrollToBottom(); } else { typewrite(bubble, text, 0); }
  }
  function typewrite(el, text, index) {
    if (index >= text.length) { scrollToBottom(); return; }
    const chunk = text.length > 400 ? 4 : 1; const end = Math.min(index + chunk, text.length);
    el.textContent = text.slice(0, end); const delay = text.length > 600 ? 10 : 18;
    scrollToBottom(); setTimeout(function () { typewrite(el, text, end); }, delay);
  }
  async function sendMessage() {
    const text = inp.value.trim(); if (!text || isBusy) return;
    isBusy = true; sendBtn.disabled = true; inp.disabled = true;
    removeEmptyState(); appendUserBubble(text); inp.value = ''; resizeInp(); showThinking();
    try {
      const res = await fetch('/api/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message: text }) });
      if (!res.ok) throw new Error('서버 오류 (HTTP ' + res.status + ')');
      const data = await res.json(); removeThinking();
      appendAiBubble(data.answer || '(응답 없음)', data.label || '', false);
    } catch (err) {
      removeThinking(); appendAiBubble('응답을 받아오는 중 오류가 발생했습니다.\n' + err.message, '', true);
    } finally { isBusy = false; sendBtn.disabled = false; inp.disabled = false; inp.focus(); }
  }
  sendBtn.addEventListener('click', sendMessage);
  inp.addEventListener('keydown', function (e) { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); } });
  document.querySelectorAll('.chip').forEach(function (chip) {
    chip.addEventListener('click', function () { if (isBusy) return; inp.value = chip.dataset.q; resizeInp(); sendMessage(); });
  });
  inp.focus();
})();
</script>
</body>
</html>
"""

_PAGE = _INDEX_HTML.replace("{{EMBLEM}}", _EMBLEM_SVG)


# ── UI 미리보기(mock) 백엔드 — 무거운 모델/검색 없이 UI만 확인(UI_MOCK=1) ──
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
        name = "식단"
    elif any(k in q for k in ("셔틀", "버스", "정류장", "통학")):
        name = "통학/셔틀"
    elif any(k in q for k in ("졸업", "학점", "전공")):
        name = "졸업요건"
    elif any(k in q for k in ("수강", "정정", "계절", "일정", "학기")):
        name = "학사일정"
    else:
        name = "학교공지"
    ans = _MOCK_ANSWER[name] + "\n\n(UI 미리보기 모드 — 실제 모델/검색 미로딩)"
    if return_meta:
        return ans, {"label": -1, "label_name": name, "categories": []}
    return ans


def _build_app(backend):
    """FastAPI 앱: GET / 페이지, POST /api/chat 응답(backend=chat_answer 또는 mock)."""
    import json as _json
    from fastapi import FastAPI, Request
    from fastapi.responses import HTMLResponse, JSONResponse
    from starlette.concurrency import run_in_threadpool

    app = FastAPI(title="CNU Campus ChatBot")

    @app.get("/", response_class=HTMLResponse)
    def _index():
        return _PAGE

    @app.post("/api/chat")
    async def _chat(request: Request):
        try:
            raw = await request.body()
            data = _json.loads(raw.decode("utf-8")) if raw else {}
        except Exception:
            data = {}
        message = (data or {}).get("message", "")
        try:
            # 동기 백엔드(EXAONE 등)는 threadpool 에서 실행해 이벤트루프 비차단.
            ans, meta = await run_in_threadpool(backend, message, True)
            return {"answer": ans or "", "label": (meta or {}).get("label_name", "") or ""}
        except Exception as e:
            return JSONResponse({"answer": f"오류가 발생했습니다: {e}", "label": ""})

    return app


# ── cloudflared 퀵터널(토큰 불필요) — 콜랩 공개 링크 ──────────────────────
def _ensure_cloudflared():
    p = shutil.which("cloudflared")
    if p:
        return p
    local = str(ROOT / "cloudflared")
    if os.path.exists(local):
        return local
    try:
        url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
        print("[ui] cloudflared 내려받는 중…(공개 링크용)")
        urllib.request.urlretrieve(url, local)
        os.chmod(local, os.stat(local).st_mode | stat.S_IEXEC)
        return local
    except Exception as e:
        print(f"[ui] cloudflared 준비 실패: {e}")
        return None


def _wait_port(port: int, timeout: int = 40) -> bool:
    for _ in range(timeout * 2):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.5)
    return False


def _tunnel(port: int):
    if not _wait_port(port):
        print("[ui] 서버 시작 대기 실패")
        return
    if os.name == "nt":
        print(f"[ui] (윈도우) 공개터널 생략 — 로컬 http://localhost:{port}")
        return
    cf = _ensure_cloudflared()
    if not cf:
        print(f"[ui] 공개 링크 불가 — 로컬 http://localhost:{port} 사용")
        return
    try:
        proc = subprocess.Popen(
            [cf, "tunnel", "--url", f"http://localhost:{port}", "--no-autoupdate"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
        )
    except Exception as e:
        print(f"[ui] cloudflared 실행 실패: {e}")
        return
    globals()["_CF_PROC"] = proc
    for line in iter(proc.stdout.readline, ""):
        m = re.search(r"https://[-a-z0-9.]+\.trycloudflare\.com", line)
        if m:
            print("\n" + "=" * 64)
            print("  공개 링크(클릭):", m.group(0))
            print("=" * 64 + "\n")
            return


def launch_app(share: "bool | None" = None):
    if os.environ.get("UI_MOCK") == "1":
        backend = _mock_answer
    else:
        from src.chat_pipeline import chat_answer
        backend = chat_answer

    if share is None:
        share = (os.environ.get("GRADIO_SHARE", "0") == "1"
                 or os.environ.get("SHARE", "0") == "1")

    port = int(os.environ.get("PORT", "7860"))
    app = _build_app(backend)

    if share:
        threading.Thread(target=_tunnel, args=(port,), daemon=True).start()
    else:
        threading.Thread(
            target=lambda: (_wait_port(port) and webbrowser.open(f"http://127.0.0.1:{port}")),
            daemon=True,
        ).start()

    print(f"[ui] 로컬: http://localhost:{port}")
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")


if __name__ == "__main__":
    launch_app()
