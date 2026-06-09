@echo off
chcp 65001 >nul
REM Launch CNU ChatBot Web UI in PREVIEW (mock) mode to inspect the design.
REM No heavy model/RAG is loaded; mock answers are returned so the UI is interactive.
REM A browser opens automatically. Public link also printed (gradio.live).
setlocal
set "UI_MOCK=1"
set "GRADIO_SHARE=1"
echo === CNU ChatBot UI preview (mock backend) ===
echo Local:  http://127.0.0.1:7860
echo (A public gradio.live link will also be printed below.)
py src\chatbot_ui.py
pause
