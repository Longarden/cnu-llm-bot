@echo off
chcp 65001 >nul
REM Launch the custom FastAPI chat UI in PREVIEW (mock) mode to inspect the design.
REM No heavy model/RAG is loaded; mock answers are returned. Browser opens automatically.
setlocal
pushd "%~dp0.."
set "UI_MOCK=1"
set "GRADIO_SHARE=0"
echo === CNU ChatBot UI preview (custom FastAPI, mock backend) ===
echo Open: http://127.0.0.1:7860
py src\chatbot_ui.py
popd
pause
