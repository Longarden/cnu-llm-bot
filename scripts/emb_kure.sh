#!/bin/bash
# GPU0에서 600메모(contextual_chunks.json) KURE(한국어특화) 임베딩.
cd /workspace/cnu-llm-bot
export CUDA_VISIBLE_DEVICES=0
export EMB_MODEL=nlpai-lab/KURE-v1
export USE_CONTEXTUAL=1
export CTX_OUT=data/contextual_chunks.json
export EMB_TAG=_600kure
nohup python -u scripts/run_embed_p100.py > data/planner/emb_600kure.log 2>&1 &
echo "started PID $!"
