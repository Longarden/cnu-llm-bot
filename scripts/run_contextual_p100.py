"""P100 서버 전용 — W1 Contextual Retrieval prefix 생성 (오프라인 전처리).

콜랩 T4에서 ~3시간 걸리던 셀5를 P100이 대신 처리. 산출물(json)만 git push →
콜랩은 그 json 받아 임베딩만 하면 됨 (추론환경 T4와 무관한 전처리 산출물).

P100(compute 6.0)은 AWQ 불가 → 비양자화 FP16 Qwen 3B 사용.
필요 패키지: torch, transformers, accelerate, sentencepiece (chromadb 등 불필요).

실행:
  export CUDA_VISIBLE_DEVICES=0   # 12GB free인 GPU만 사용
  cd /workspace/cnu-llm-bot
  nohup python scripts/run_contextual_p100.py > data/planner/ctx_p100.log 2>&1 &
  tail -f data/planner/ctx_p100.log

끊겨도 다시 실행하면 contextual_chunks.json 에서 resume.
"""
import sys, os, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

from embedding.data_loader import load_scoped_docs
from embedding.chunker import chunk_documents
from retrieval.contextual_chunker import contextualize_chunks

MODEL_ID = os.environ.get("CTX_MODEL", "Qwen/Qwen2.5-3B-Instruct")  # FP16 (AWQ 아님)
OUT = os.environ.get("CTX_OUT", str(ROOT / "data" / "contextual_chunks.json"))
MAX_NEW = int(os.environ.get("CTX_MAX_NEW", "120"))


def main():
    print(f"=== P100 contextual prefix 생성 ===", flush=True)
    print(f"  CUDA_VISIBLE_DEVICES={os.environ.get('CUDA_VISIBLE_DEVICES','(unset)')}", flush=True)
    print(f"  torch {torch.__version__}  cuda_avail={torch.cuda.is_available()}", flush=True)
    if torch.cuda.is_available():
        print(f"  device: {torch.cuda.get_device_name(0)}", flush=True)
    print(f"  model: {MODEL_ID}", flush=True)

    t0 = time.time()
    tok = AutoTokenizer.from_pretrained(MODEL_ID)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID, torch_dtype=torch.float16
    ).to("cuda")
    model.eval()
    pad_id = tok.pad_token_id or tok.eos_token_id
    print(f"  모델 로딩 {time.time()-t0:.0f}s", flush=True)

    @torch.no_grad()
    def llm_call(prompt: str, max_new_tokens: int = MAX_NEW) -> str:
        msgs = [{"role": "user", "content": prompt}]
        try:
            enc = tok.apply_chat_template(
                msgs, add_generation_prompt=True, return_tensors="pt", return_dict=True
            )
            input_ids = enc["input_ids"].to("cuda")
            attn = enc.get("attention_mask")
            attn = attn.to("cuda") if attn is not None else None
        except Exception:
            input_ids = tok.apply_chat_template(
                msgs, add_generation_prompt=True, return_tensors="pt"
            ).to("cuda")
            attn = None
        out = model.generate(
            input_ids, attention_mask=attn, max_new_tokens=max_new_tokens,
            do_sample=False, pad_token_id=pad_id,
        )
        return tok.decode(out[0][input_ids.shape[1]:], skip_special_tokens=True)

    # 데이터 로드 + 청킹
    docs = load_scoped_docs()
    chunks = chunk_documents(docs)
    print(f"  docs {len(docs)}  chunks {len(chunks)}", flush=True)

    # 컨텍스트 생성 (resume + checkpoint)
    t1 = time.time()
    ctx = contextualize_chunks(
        docs, chunks, llm_call,
        out_path=OUT, checkpoint_every=200, resume=True,
    )
    ok = sum(1 for c in ctx if c.get("context_prefix"))
    dt = time.time() - t1
    print(f"\n=== 완료 ===", flush=True)
    print(f"  컨텍스트 prefix: {ok}/{len(ctx)}", flush=True)
    print(f"  소요 {dt/60:.1f}분  ({dt/max(len(chunks),1):.2f}s/청크)", flush=True)
    print(f"  저장: {OUT}", flush=True)


if __name__ == "__main__":
    main()
