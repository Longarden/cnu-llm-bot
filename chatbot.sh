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
# 생성 토큰 상한: 256 은 졸업요건·셔틀 같은 긴 답이 중간에 잘림 → 512 로 상향(잘림 방지).
export MAX_NEW_TOKENS="${MAX_NEW_TOKENS:-512}"
# CUDA 단편화 방지(에러 메시지 권장값).
export PYTORCH_CUDA_ALLOC_CONF="${PYTORCH_CUDA_ALLOC_CONF:-expandable_segments:True}"
# 라이브 크롤 타임아웃: (connect 4초, read 15초) 분리. 죽은 호스트는 빨리 포기, 느린 plus.cnu는 기다림.
export CRAWL_CONNECT_TIMEOUT="${CRAWL_CONNECT_TIMEOUT:-4}"
export CRAWL_TIMEOUT="${CRAWL_TIMEOUT:-15}"
export CRAWL_RETRIES="${CRAWL_RETRIES:-0}"

# 의존성 보장: 채점 Colab 기본 torch가 사양(2.5.1)과 다르면 requirements 설치(torch 핀이 실제 적용되게).
# 이미 2.5.1 이면 건너뜀(빠름). torch import 없이 메타데이터 버전만 확인.
if ! python -c "import importlib.metadata as m,sys; sys.exit(0 if m.version('torch')=='2.5.1' else 1)" 2>/dev/null; then
  echo "[chatbot.sh] torch 사양 불일치 → requirements 설치(torch 2.5.1 등)"
  pip install -q -r requirements.txt || echo "[chatbot.sh] 경고: requirements 설치 일부 실패(계속 진행)"
fi

# chat 배치 + realtime 배치 + UI 를 '단일 프로세스'(run_all.py)로 실행 → 생성모델 7B 를 1회만 로드.
#   (기존엔 python 3번 호출 → 7B 3번 로드, 콜랩에서 로딩만 ~5분 낭비 + 포트/GPU 충돌). 이미 산출물이
#   있으면 배치는 run_all 내부에서 건너뜀. 강제 재생성: FORCE_BATCH=1 bash chatbot.sh.
#   콜랩: cloudflared 미사용 → 좌측 '포트(Ports)' 탭에서 7860(100초 524 캡 없음). 외부 URL은 GRADIO_SHARE=1.
echo "[chatbot.sh] 단일 프로세스 실행(run_all): chat+realtime 배치 → UI (7B 1회 로드)"
python src/run_all.py
