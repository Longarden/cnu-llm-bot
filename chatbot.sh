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
# 진짜 외부 공개 URL이 필요하면 GRADIO_SHARE=1 bash chatbot.sh 로 cloudflared 를 켤 수 있다.
export GRADIO_SHARE="${GRADIO_SHARE:-0}"
# 리랭커(CrossEncoder bge-reranker-v2-m3) 켬 = 검색정밀도+CRAG 거절게이트 활성. T4 메모리 빠듯하면 RERANK=0 bash chatbot.sh 로 끌 수 있음.
export RERANK="${RERANK:-1}"
# 라이브 시연 안정성: 기본 생성모델 = EXAONE-3.5-2.4B(4bit ≈ 1.8GB). T4에 8~10GB 여유 → OOM 거의 불가.
# 품질용 7.8B가 필요하면 MODEL_PRIMARY_NAME=LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct bash chatbot.sh 로 덮어쓰기.
export MODEL_PRIMARY_NAME="${MODEL_PRIMARY_NAME:-LGAI-EXAONE/EXAONE-3.5-2.4B-Instruct}"
# CUDA 단편화 방지(에러 메시지 권장값). reserved-but-unallocated 조각으로 인한 OOM 완화.
export PYTORCH_CUDA_ALLOC_CONF="${PYTORCH_CUDA_ALLOC_CONF:-expandable_segments:True}"
# 라이브 크롤 타임아웃 짧게: 느리거나 죽은 학과서버 한 곳이 100초 터널 한도를 먹어 524 내는 것 방지.
# (느린 서버는 8초에 포기하고 정적 폴백 → 524 대신 즉시 답). 학과 공지서버가 자주 느림.
export CRAWL_TIMEOUT="${CRAWL_TIMEOUT:-12}"
export CRAWL_RETRIES="${CRAWL_RETRIES:-0}"

# Task2/Task3 배치(outputs/*.json)는 노트북(ipynb)에서 미리 생성하므로 여기서는 만들지 않고
# UI를 바로 띄운다(시연 빠름). 수동 재생성이 필요하면:
#   python src/gen_chat_output.py && python src/realtime_model.py

# (3) 커스텀 FastAPI UI 실행 (분류 라우팅 포함 챗봇).
#     콜랩: cloudflared 미사용 → 좌측 '포트(Ports)' 탭에서 7860 열기(100초 524 캡 없음).
#     커널 셀에서 띄우면 proxyPort 링크가 자동 출력됨. 외부 공개 URL은 GRADIO_SHARE=1 로.
echo "[chatbot.sh] 챗봇 UI 실행 — 콜랩 좌측 '포트' 탭에서 7860 을 여세요(공개링크는 자동 안내)"
python src/chatbot_ui.py
