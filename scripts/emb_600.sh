#!/bin/bash
# GPU0에서 600메모(contextual_chunks.json) bge-m3 임베딩. 긴 명령 캡슐화.
cd /workspace/cnu-llm-bot
export CUDA_VISIBLE_DEVICES=0
export EMB_MODEL=BAAI/bge-m3
export USE_CONTEXTUAL=1
export CTX_OUT=data/contextual_chunks.json
export EMB_TAG=_600bge
nohup python -u scripts/run_embed_p100.py > data/planner/emb_600bge.log 2>&1 &
echo "started PID $!"
