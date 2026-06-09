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

# 로컬 생성 강제(외부 API 금지) + 실시간 라이브크롤 ON
export GEN_BACKEND="${GEN_BACKEND:-local}"
export CHAT_REALTIME="${CHAT_REALTIME:-1}"
# 공개링크: 기본은 cloudflared 미사용(=콜랩 프록시). cloudflared 퀵터널은 origin 100초 한도라
# 느린 라이브 답변에서 524를 냈다. 콜랩에서는 좌측 '포트' 탭(또는 proxyPort)으로 열면 캡이 없다.
export GRADIO_SHARE="${GRADIO_SHARE:-0}"
# 리랭커(CrossEncoder bge-reranker-v2-m3) 켬 = 검색정밀도+CRAG 거절게이트 활성.
export RERANK="${RERANK:-1}"
# 생성모델: 품질 위해 EXAONE-3.5-7.8B(4bit). 임베더/리랭커는 CPU로 내려 VRAM 확보 → T4에서 7.8B OOM 방지.
# (7.8B 5.5GB + 임베더/리랭커 GPU 4.6GB 동시면 T4 빠듯 → 둘을 CPU로 빼서 여유 확보)
export MODEL_PRIMARY_NAME="${MODEL_PRIMARY_NAME:-LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct}"
export EMBED_DEVICE="${EMBED_DEVICE:-cpu}"
export RERANK_DEVICE="${RERANK_DEVICE:-cpu}"
# CUDA 단편화 방지(에러 메시지 권장값).
export PYTORCH_CUDA_ALLOC_CONF="${PYTORCH_CUDA_ALLOC_CONF:-expandable_segments:True}"
# 라이브 크롤 타임아웃: (connect 4초, read 15초) 분리. 죽은 호스트는 빨리 포기, 느린 plus.cnu는 기다림.
export CRAWL_CONNECT_TIMEOUT="${CRAWL_CONNECT_TIMEOUT:-4}"
export CRAWL_TIMEOUT="${CRAWL_TIMEOUT:-15}"
export CRAWL_RETRIES="${CRAWL_RETRIES:-0}"

# (1) Task2 배치: data/test_chat.json → outputs/chat_output.json
#     PDF 요구: 평가 시 chatbot.sh "만" 실행해도 산출물이 나와야 함. 이미 있으면 건너뜀(시연 재실행 빠름).
if [ ! -s outputs/chat_output.json ]; then
  echo "[chatbot.sh] (1) Task2 배치 추론 → outputs/chat_output.json"
  python src/gen_chat_output.py || echo "[chatbot.sh] (1) 경고: chat_output 생성 오류(계속 진행)"
else
  echo "[chatbot.sh] (1) outputs/chat_output.json 이미 있음 — 배치 건너뜀(지우면 재생성)"
fi

# (2) Task3 배치: data/test_realtime.json → outputs/realtime_output.json
if [ ! -s outputs/realtime_output.json ]; then
  echo "[chatbot.sh] (2) Task3 실시간반영 → outputs/realtime_output.json"
  python src/realtime_model.py || echo "[chatbot.sh] (2) 경고: realtime_output 생성 오류(계속 진행)"
else
  echo "[chatbot.sh] (2) outputs/realtime_output.json 이미 있음 — 배치 건너뜀(지우면 재생성)"
fi

# (3) 챗봇 UI 실행 (분류 라우팅 포함).
#     콜랩: cloudflared 미사용 → 좌측 '포트(Ports)' 탭에서 7860 열기(100초 524 캡 없음).
#     커널 셀에서 띄우면 proxyPort 링크 자동 출력. 외부 공개 URL은 GRADIO_SHARE=1 로.
echo "[chatbot.sh] (3) 챗봇 UI 실행 — 콜랩 좌측 '포트' 탭에서 7860 을 여세요(공개링크 자동 안내)"
python src/chatbot_ui.py
