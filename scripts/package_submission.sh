#!/usr/bin/env bash
# CNU Campus ChatBot — 제출물 패키징 스크립트 (PDF p20 디렉토리 사양)
#
# 레포의 기존 파일들을 과제 필수 레이아웃의 staging 폴더로 복사/배치하고 zip 생성.
#
# 사용법:
#   TEAM=조이름 NAME=홍길동 bash scripts/package_submission.sh
#   bash scripts/package_submission.sh                 # 기본값(TEAM/NAME 미지정) 사용
#   bash scripts/package_submission.sh MyTeam 홍길동    # 인자로 TEAM, NAME 지정
#
# 결과:
#   dist/Termproject_<NAME>/   ... 제출 디렉토리 구조(스테이징)
#   dist/Termproject_<NAME>.zip ... 제출용 zip
#
# 필수 레이아웃(PDF p20, 빨간 경로 그대로):
#   Termproject_{이름}/
#     data/{test_cls.json, test_chat.json}
#     src/{classifier.ipynb, chatbot_ui.py, realtime_model.py,
#          chat_pipeline.py, gen_chat_output.py, classifier.py}
#     model/model.bin
#     chatbot.sh
#     outputs/{cls_output.json, chat_output.json, realtime_output.json}
#     requirements.txt
#     README.md
#
# 평가 시 채점자는 classifier.ipynb 와 chatbot.sh 만 실행한다(PDF p20).
set -euo pipefail

# 스크립트 위치 기준으로 프로젝트 루트 계산(어디서 호출해도 동작)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

# ── 파라미터: 인자 > 환경변수 > 기본값 ──────────────────────────────
TEAM="${1:-${TEAM:-TEAM}}"
NAME="${2:-${NAME:-이름}}"

STAGE_NAME="Termproject_${NAME}"
DIST="$ROOT/dist"
STAGE="$DIST/$STAGE_NAME"
ZIP_PATH="$DIST/${STAGE_NAME}.zip"

echo "[package] TEAM=$TEAM  NAME=$NAME"
echo "[package] staging: $STAGE"

# ── 스테이징 초기화 ─────────────────────────────────────────────────
rm -rf "$STAGE"
mkdir -p "$STAGE/data" "$STAGE/src" "$STAGE/model" "$STAGE/outputs"

# 파일 복사 헬퍼: 원본 없으면 경고만(빌드 중단 안 함)
copy_one() {  # copy_one <src> <dst>
  local src="$1" dst="$2"
  if [ -f "$src" ]; then
    cp -f "$src" "$dst"
  else
    echo "[warn] 누락(스킵): $src"
  fi
}

# ── data/ : 평가용 테스트셋 ─────────────────────────────────────────
copy_one "$ROOT/data/test_cls.json"  "$STAGE/data/test_cls.json"
copy_one "$ROOT/data/test_chat.json" "$STAGE/data/test_chat.json"
# (옵션) Task3 실시간 테스트셋도 있으면 같이 동봉
copy_one "$ROOT/data/test_realtime.json" "$STAGE/data/test_realtime.json"

# ── src/ : 필수 6개 소스 ────────────────────────────────────────────
for f in classifier.ipynb chatbot_ui.py realtime_model.py \
         chat_pipeline.py gen_chat_output.py classifier.py; do
  copy_one "$ROOT/src/$f" "$STAGE/src/$f"
done

# ── chatbot.sh / requirements.txt / README.md ──────────────────────
copy_one "$ROOT/chatbot.sh"        "$STAGE/chatbot.sh"
copy_one "$ROOT/requirements.txt"  "$STAGE/requirements.txt"
copy_one "$ROOT/README.md"         "$STAGE/README.md"
copy_one "$ROOT/restore_assets.sh" "$STAGE/restore_assets.sh"
copy_one "$ROOT/.gitattributes"    "$STAGE/.gitattributes"
chmod +x "$STAGE/chatbot.sh" "$STAGE/restore_assets.sh" 2>/dev/null || true

# ── 챗봇 파이프라인 실행에 필요한 지원 패키지 동봉 ───────────────────
#   src/*.py 가 import 하는 내부 모듈들. 이게 없으면 chatbot.sh 가 실행 불가.
#   (PDF 필수 레이아웃 외 보조 자료. 평가 환경에서 import 경로 보존.)
for pkg in interface retrieval generation embedding crawlers crawler_pipeline; do
  if [ -d "$ROOT/$pkg" ]; then
    # __pycache__ 제외하고 복사
    mkdir -p "$STAGE/$pkg"
    (cd "$ROOT" && find "$pkg" -type f ! -path '*__pycache__*' -print0 \
       | while IFS= read -r -d '' rel; do
           mkdir -p "$STAGE/$(dirname "$rel")"
           cp -f "$rel" "$STAGE/$rel"
         done)
  fi
done

# ── model/ : 분류기 가중치 ──────────────────────────────────────────
#   model.bin 은 용량이 커서(약 422MB) zip 동봉이 비현실적일 수 있다.
#   기본은 placeholder(다운로드 링크 안내)로 대체. INCLUDE_MODEL=1 이면 실제 복사.
MODEL_BIN="$ROOT/model/model.bin"
if [ "${INCLUDE_MODEL:-0}" = "1" ] && [ -f "$MODEL_BIN" ]; then
  echo "[package] 분류기 가중치 실제 동봉(INCLUDE_MODEL=1, safetensors)"
  # safetensors 우선. model.bin 은 제외(safetensors 와 중복 422MB + CVE-2025-32434 .bin 차단 회피).
  for mf in model.safetensors config.json label_map.json special_tokens_map.json \
            tokenizer.json tokenizer_config.json vocab.txt; do
    copy_one "$ROOT/model/$mf" "$STAGE/model/$mf"
  done
else
  # placeholder: 용량 큰 가중치는 드라이브 링크로 대체(restore_assets.sh 로 복원)
  cat > "$STAGE/model/DOWNLOAD_MODEL.txt" <<'PLACEHOLDER'
=== 분류기 가중치(model.safetensors)는 용량이 커서 zip 에서 제외했습니다 ===

복원 방법 (둘 중 하나):
  1) restore_assets.sh 의 MODEL_ID 를 드라이브 파일ID로 채운 뒤:  bash restore_assets.sh
  2) 수동: model.tar.gz 를 드라이브에서 받아 압축해제 → model/ 에 safetensors+config+tokenizer 배치

드라이브 링크(채워넣기): <model.tar.gz 공유 링크>

(zip 에 실제 가중치까지 동봉하려면:  INCLUDE_MODEL=1 bash scripts/package_submission.sh)
PLACEHOLDER
  echo "[package] model.bin → placeholder(다운로드 링크 안내) 생성"
  # placeholder 모드에서도 토크나이저/설정은 가벼우니 동봉(분류기 로드용)
  for mf in config.json label_map.json special_tokens_map.json \
            tokenizer.json tokenizer_config.json vocab.txt; do
    copy_one "$ROOT/model/$mf" "$STAGE/model/$mf"
  done
fi

# ── chroma_db/ : RAG 벡터DB. 챗봇 검색에 필수. 작아서(약 13MB) 기본 동봉. ──
#   INCLUDE_CHROMA=0 으로 끄면 드라이브 복원(restore_assets.sh)에 의존.
if [ "${INCLUDE_CHROMA:-1}" = "1" ] && [ -d "$ROOT/chroma_db" ]; then
  echo "[package] chroma_db/ 동봉(벡터DB)"
  (cd "$ROOT" && find chroma_db -type f ! -path '*__pycache__*' -print0 \
     | while IFS= read -r -d '' rel; do
         mkdir -p "$STAGE/$(dirname "$rel")"
         cp -f "$rel" "$STAGE/$rel"
       done)
else
  echo "[package] chroma_db/ 미동봉 → 드라이브 복원 의존(restore_assets.sh)"
fi

# ── outputs/ : 평가 시 생성됨. 빈 폴더라도 존재해야 함 ──────────────
#   .gitkeep 으로 빈 디렉토리 보존(zip 에 폴더가 남도록).
touch "$STAGE/outputs/.gitkeep"

# ── zip 생성 ────────────────────────────────────────────────────────
rm -f "$ZIP_PATH"
if command -v zip >/dev/null 2>&1; then
  (cd "$DIST" && zip -rq "${STAGE_NAME}.zip" "$STAGE_NAME")
  echo "[package] zip 생성: $ZIP_PATH"
else
  # zip 미설치 환경(Windows Git-Bash 등) → python 으로 폴백
  python - "$DIST" "$STAGE_NAME" <<'PYZIP'
import sys, shutil, os
dist, name = sys.argv[1], sys.argv[2]
out = os.path.join(dist, name)
shutil.make_archive(out, 'zip', root_dir=dist, base_dir=name)
print(f"[package] (python) zip 생성: {out}.zip")
PYZIP
fi

# ── 결과 트리 출력 ──────────────────────────────────────────────────
echo ""
echo "[package] === 제출 디렉토리 구조 ==="
if command -v tree >/dev/null 2>&1; then
  tree -F "$STAGE"
else
  (cd "$DIST" && find "$STAGE_NAME" -not -path '*__pycache__*' | sort | sed 's|[^/]*/|  |g')
fi

echo ""
echo "[package] 완료. 제출물: $ZIP_PATH"
