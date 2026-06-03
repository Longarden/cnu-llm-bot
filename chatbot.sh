#!/usr/bin/env bash
# CNU Campus ChatBot — 평가용 실행 스크립트 (PDF: 평가 시 classifier.ipynb 와 chatbot.sh 만 실행)
# 흐름: (1) data/test_chat.json    → outputs/chat_output.json      (Task2 필수)
#       (2) data/test_realtime.json → outputs/realtime_output.json  (Task3 옵션 +30)
#       (3) Gradio ChatInterface UI 실행 (질문 입력 / 응답 출력 / 대화 흐름)
# 챗봇: 질문 → 질문유형 분류기(model/) → data_category 소프트 라우팅 RAG/라이브크롤 → EXAONE 생성.
# 완전 로컬(외부 API 금지). 생성 백엔드 generation/llm.py GEN_BACKEND=local(기본 EXAONE).

# 스크립트 위치를 프로젝트 루트로 (어디서 호출해도 동작)
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

# 로컬 생성 강제(외부 API 금지) + 실시간 라이브크롤 ON + 콜랩 공유링크 발급
export GEN_BACKEND="${GEN_BACKEND:-local}"
export CHAT_REALTIME="${CHAT_REALTIME:-1}"
export GRADIO_SHARE="${GRADIO_SHARE:-1}"

# 주의: JSON 생성 단계가 실패해도(예: 일시적 크롤 실패) UI는 반드시 뜨도록 비차단(set -e 미사용).

# (1) Task2 배치 추론: data/test_chat.json → outputs/chat_output.json [{"user","model"}]
echo "[chatbot.sh] (1) Task2 배치 추론 → outputs/chat_output.json"
python src/gen_chat_output.py || echo "[chatbot.sh] (1) 경고: chat_output 생성 중 오류(계속 진행)"

# (2) Task3 실시간반영: data/test_realtime.json → outputs/realtime_output.json [{"user","model"}]
#     셔틀/식단/공지를 라이브 크롤해 최신 정보로 답변. 네트워크 실패 시 폴백 메시지로 채움.
echo "[chatbot.sh] (2) Task3 실시간반영 → outputs/realtime_output.json"
python src/realtime_model.py || echo "[chatbot.sh] (2) 경고: realtime_output 생성 중 오류(계속 진행)"

# (3) Gradio UI 실행 (분류 라우팅 포함 챗봇). 콜랩에서는 출력되는 *.gradio.live 링크로 접속.
echo "[chatbot.sh] (3) Gradio UI 실행"
python src/chatbot_ui.py
