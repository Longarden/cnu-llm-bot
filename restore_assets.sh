#!/usr/bin/env bash
# 드라이브에서 model/ + chroma_db/ 복원 (용량 큰 자산은 깃/zip 대신 구글드라이브 링크로 배포).
# 사용: bash restore_assets.sh
#
# 사전 준비: 아래 두 ID를 본인 구글드라이브 공유링크의 파일ID로 교체.
#   드라이브에서 model.tar.gz / chroma_db.tar.gz 를 "링크가 있는 모든 사용자: 뷰어"로 공유한 뒤
#   링크 https://drive.google.com/file/d/<여기가_ID>/view 의 <ID> 부분을 붙여넣는다.
set -euo pipefail
cd "$(dirname "$0")"

MODEL_ID="YOUR_MODEL_TAR_GZ_FILE_ID"      # model.tar.gz 의 구글드라이브 파일ID
CHROMA_ID="YOUR_CHROMA_TAR_GZ_FILE_ID"    # chroma_db.tar.gz 의 구글드라이브 파일ID

pip install -q gdown

if [ ! -d model ]; then
  echo "[restore] model/ 없음 → 드라이브에서 받기"
  gdown "https://drive.google.com/uc?id=${MODEL_ID}" -O model.tar.gz
  tar xzf model.tar.gz && rm -f model.tar.gz
else
  echo "[restore] model/ 이미 있음 — 스킵"
fi

if [ ! -d chroma_db ]; then
  echo "[restore] chroma_db/ 없음 → 드라이브에서 받기"
  gdown "https://drive.google.com/uc?id=${CHROMA_ID}" -O chroma_db.tar.gz
  tar xzf chroma_db.tar.gz && rm -f chroma_db.tar.gz
else
  echo "[restore] chroma_db/ 이미 있음 — 스킵"
fi

echo "[restore] 완료. model/ 와 chroma_db/ 준비됨."
ls -d model chroma_db 2>/dev/null || true
