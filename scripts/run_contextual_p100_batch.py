"""P100 서버 전용 — W1 Contextual prefix 생성 (배치 가속판).

순차판(run_contextual_p100.py)은 19860청크 × 1건씩 = ~4시간.
이 배치판은 BATCH개씩 묶어 generate → ~40분. 산출물 포맷 동일(콜랩 호환).

P100(compute 6.0) FP16 Qwen 3B. 같은 out_path로 resume.

실행:
  export CUDA_VISIBLE_DEVICES=0
  cd /workspace/cnu-llm-bot
  nohup python scripts/run_contextual_p100_batch.py > data/planner/ctx_batch.log 2>&1 &
  echo "PID $!"; sleep 60; tail -30 data/planner/ctx_batch.log

env 조정: CTX_BATCH(기본16, OOM이면 8), CTX_MAX_NEW(기본80).
"""
import sys, os, json, time, math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

from embedding.data_loader import load_scoped_docs
from embedding.chunker import chunk_documents
from retrieval.contextual_chunker import _CTX_PROMPT

MODEL_ID = os.environ.get("CTX_MODEL", "Qwen/Qwen2.5-3B-Instruct")
OUT = os.environ.get("CTX_OUT", str(ROOT / "data" / "contextual_chunks.json"))
BATCH = int(os.environ.get("CTX_BATCH", "16"))
MAX_NEW = int(os.environ.get("CTX_MAX_NEW", "80"))
DOC_HEAD = int(os.environ.get("CTX_DOC_HEAD", "600"))
CHUNK_CAP = int(os.environ.get("CTX_CHUNK_CAP", "700"))


def clean_ctx(s: str) -> str:
    s = (s or "").strip().split("\n", 1)[0].strip(" -*[]()\t")
    return s if 10 <= len(s) <= 200 else ""


def main():
    print("=== P100 contextual prefix 생성 (배치판) ===", flush=True)
    print(f"  CUDA_VISIBLE_DEVICES={os.environ.get('CUDA_VISIBLE_DEVICES','(unset)')}", flush=True)
    print(f"  torch {torch.__version__}  cuda_avail={torch.cuda.is_available()}", flush=True)
    if torch.cuda.is_available():
        print(f"  device: {torch.cuda.get_device_name(0)}", flush=True)
    print(f"  model: {MODEL_ID}  BATCH={BATCH}  MAX_NEW={MAX_NEW}", flush=True)

    t0 = time.time()
    tok = AutoTokenizer.from_pretrained(MODEL_ID)
    tok.padding_side = "left"
    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token
    load_8bit = os.environ.get("CTX_LOAD_8BIT", "0") == "1"
    if load_8bit:
        # 7B는 FP16(14GB)이 P100 12GB free에 안 들어감 → 8bit(~8GB).
        from transformers import BitsAndBytesConfig
        bnb = BitsAndBytesConfig(load_in_8bit=True)
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_ID, quantization_config=bnb, device_map="cuda"
        )
        print("  (8bit 로딩)", flush=True)
    else:
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_ID, torch_dtype=torch.float16
        ).to("cuda")
    model.eval()
    print(f"  모델 로딩 {time.time()-t0:.0f}s", flush=True)

    docs = load_scoped_docs()
    chunks = chunk_documents(docs)
    doc_map = {d.get("source_url", ""): d for d in docs}
    print(f"  docs {len(docs)}  chunks {len(chunks)}", flush=True)

    def make_text(chunk: dict) -> str:
        d = doc_map.get(chunk.get("source_url", ""), {})
        prompt = _CTX_PROMPT.format(
            title=(d.get("title", "") or "")[:120],
            doc_head=(d.get("original_text", "") or d.get("content", "") or "")[:DOC_HEAD],
            chunk=(chunk.get("original_text", "") or "")[:CHUNK_CAP],
        )
        return tok.apply_chat_template(
            [{"role": "user", "content": prompt}], tokenize=False, add_generation_prompt=True
        )

    # resume
    out_list = []
    if os.path.exists(OUT):
        try:
            out_list = json.load(open(OUT, encoding="utf-8"))
            print(f"  resume: {len(out_list)}/{len(chunks)} 이미 완료", flush=True)
        except Exception:
            out_list = []
    start = len(out_list)
    ok = sum(1 for x in out_list if x.get("context_prefix"))

    n_batches = math.ceil((len(chunks) - start) / BATCH)
    t1 = time.time()
    bi = 0
    for i in range(start, len(chunks), BATCH):
        batch = chunks[i:i + BATCH]
        texts = [make_text(c) for c in batch]
        enc = tok(texts, return_tensors="pt", padding=True, truncation=True, max_length=1536).to("cuda")
        with torch.no_grad():
            gen = model.generate(**enc, max_new_tokens=MAX_NEW, do_sample=False,
                                 pad_token_id=tok.pad_token_id)
        new_tokens = gen[:, enc["input_ids"].shape[1]:]
        decoded = tok.batch_decode(new_tokens, skip_special_tokens=True)
        for c, raw in zip(batch, decoded):
            prefix = clean_ctx(raw)
            nc = dict(c)
            if prefix:
                ctext = c.get("original_text", "") or ""
                nc["context_prefix"] = prefix
                nc["original_text"] = f"{prefix}\n\n{ctext}"
                nc["content"] = nc["original_text"]
                ok += 1
            out_list.append(nc)
        bi += 1
        if bi % 10 == 0 or i + BATCH >= len(chunks):
            done = len(out_list)
            el = time.time() - t1
            rate = (done - start) / max(el, 1)
            eta = (len(chunks) - done) / max(rate, 1e-6)
            print(f"  {done}/{len(chunks)}  prefix={ok}  {rate:.1f}청크/s  ETA {eta/60:.0f}분", flush=True)
            with open(OUT, "w", encoding="utf-8") as f:
                json.dump(out_list, f, ensure_ascii=False, indent=2)

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out_list, f, ensure_ascii=False, indent=2)
    dt = time.time() - t1
    print(f"\n=== 완료 ===", flush=True)
    print(f"  prefix 생성 {ok}/{len(out_list)}  소요 {dt/60:.1f}분", flush=True)
    print(f"  저장: {OUT}", flush=True)


if __name__ == "__main__":
    main()
