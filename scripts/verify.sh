#!/usr/bin/env bash
# 제출 전 자체 검증. 모드 3가지.
#   bash scripts/verify.sh          # check : 구조/양식만(빠름, 모델 불필요)
#   bash scripts/verify.sh stub     # stub  : EXAONE 없이 파이프라인+출력양식 검증(검색까지만)
#   bash scripts/verify.sh full     # full  : 설치+분류기 학습+챗/실시간 출력 실제 생성(EXAONE 로딩)
set -uo pipefail
# 이 스크립트는 scripts/ 안에 있으므로 한 단계 위가 repo 루트다.
cd "$(dirname "$0")/.."
MODE="${1:-check}"

run() { echo; echo "▶ $*"; "$@" || echo "  [warn] 위 단계 실패(계속 진행)"; }

if [ "$MODE" = "full" ] || [ "$MODE" = "stub" ]; then
  run pip install -q -r requirements.txt

  # 분류기 가중치는 깃에 없다. classifier.py 가 없으면 그 자리에서 학습한다.
  run python src/classifier.py            # → outputs/cls_output.json

  if [ "$MODE" = "stub" ]; then
    echo "  (stub 모드: CHAT_STUB/REALTIME_STUB=1 — EXAONE 미로딩)"
    export CHAT_STUB=1 REALTIME_STUB=1
  fi
  run python src/gen_chat_output.py        # → outputs/chat_output.json
  run python src/realtime_model.py         # → outputs/realtime_output.json
fi

echo; echo "▶ 구조/양식 검증"
python scripts/verify_submission.py .
