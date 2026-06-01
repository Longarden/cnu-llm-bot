#!/usr/bin/env bash
# CNU Campus ChatBot — Task2 실행 스크립트
# 흐름: (1) data/test_chat.json 읽어 배치 추론 → outputs/chat_output.json 생성
#       (2) Gradio ChatInterface UI 실행
# 챗봇 파이프라인: 질문 → 질문유형 분류기(model/) → data_category 소프트 라우팅 RAG → EXAONE 생성.
# 완전 로컬(외부 API 금지). 생성 백엔드는 generation/llm.py GEN_BACKEND=local(기본 EXAONE).
set -e

# 스크립트 위치를 프로젝트 루트로 (어디서 호출해도 동작)
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

# 로컬 생성 강제(외부 API 금지)
export GEN_BACKEND="${GEN_BACKEND:-local}"

# (1) 배치 추론: data/test_chat.json → outputs/chat_output.json [{"user","model"}]
#     test_chat.json 없으면 스크립트가 data/cls/valid.json 에서 임시 생성.
echo "[chatbot.sh] (1) 배치 추론 → outputs/chat_output.json"
python src/gen_chat_output.py

# (2) Gradio UI 실행 (분류 라우팅 포함 챗봇)
echo "[chatbot.sh] (2) Gradio UI 실행"
python src/chatbot_ui.py
