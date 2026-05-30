"""메모 작성 모델 A/B — 청크 20개를 Qwen 7B vs EXAONE 3.5 7.8B로 각각 메모 생성.

카테고리 골고루 20개 뽑아 두 모델 메모를 나란히 출력 → 눈으로 품질 비교 후 전체 결정.
8bit 순차 로딩(메모리 절약). 결과는 화면 + data/planner/ab_compare.txt 저장.

실행:
  export CUDA_VISIBLE_DEVICES=0
  pip install -q bitsandbytes
  python scripts/compare_ctx_models.py 2>&1 | tee data/planner/ab_compare.txt
"""
import sys, os, collections
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig

from embedding.data_loader import load_scoped_docs
from embedding.chunker import chunk_documents
from retrieval.contextual_chunker import _CTX_PROMPT

N_SAMPLE = int(os.environ.get("AB_N", "20"))
QWEN = "Qwen/Qwen2.5-7B-Instruct"
EXAONE = "LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct"


def pick_samples(chunks):
    """카테고리 골고루 N개 (각 카테고리 중간 청크)."""
    by_cat = collections.defaultdict(list)
    for c in chunks:
        by_cat[c.get("data_category", "?")].append(c)
    cats = sorted(by_cat.keys())
    out, i = [], 0
    while len(out) < N_SAMPLE and any(by_cat.values()):
        cat = cats[i % len(cats)]
        if by_cat[cat]:
            lst = by_cat[cat]
            out.append(lst.pop(len(lst) // 2))
        i += 1
        if i > 10000:
            break
    return out


def make_prompt(chunk, doc_map):
    d = doc_map.get(chunk.get("source_url", ""), {})
    return _CTX_PROMPT.format(
        title=(d.get("title", "") or "")[:120],
        doc_head=(d.get("original_text", "") or "")[:600],
        chunk=(chunk.get("original_text", "") or "")[:700],
    )


def run_model(model_id, prompts, trust=False):
    print(f"\n[{model_id}] 로딩...", flush=True)
    tok = AutoTokenizer.from_pretrained(model_id, trust_remote_code=trust)
    bnb = BitsAndBytesConfig(load_in_8bit=True)
    model = AutoModelForCausalLM.from_pretrained(
        model_id, quantization_config=bnb, device_map="cuda", trust_remote_code=trust
    )
    model.eval()
    pad = tok.pad_token_id or tok.eos_token_id
    outs = []
    for p in prompts:
        msgs = [{"role": "user", "content": p}]
        ids = tok.apply_chat_template(msgs, add_generation_prompt=True, return_tensors="pt").to("cuda")
        with torch.no_grad():
            g = model.generate(ids, max_new_tokens=80, do_sample=False, pad_token_id=pad)
        txt = tok.decode(g[0][ids.shape[1]:], skip_special_tokens=True).strip()
        outs.append(txt.split("\n")[0].strip(" -*[]()"))
    del model
    torch.cuda.empty_cache()
    return outs


def main():
    docs = load_scoped_docs()
    chunks = chunk_documents(docs)
    doc_map = {d.get("source_url", ""): d for d in docs}
    sample = pick_samples(chunks)
    prompts = [make_prompt(c, doc_map) for c in sample]
    print(f"샘플 {len(sample)}개 (카테고리 골고루)", flush=True)

    qwen_out = run_model(QWEN, prompts, trust=False)
    exaone_out = run_model(EXAONE, prompts, trust=True)

    print("\n" + "=" * 70, flush=True)
    print("A/B 비교 결과 (메모 = 검색용 한 줄 맥락 요약)", flush=True)
    print("=" * 70, flush=True)
    for i, c in enumerate(sample):
        orig = (c.get("original_text", "") or "").replace("\n", " ")[:90]
        print(f"\n[{i+1}] 카테고리 {c.get('data_category')}", flush=True)
        print(f"  원문   : {orig}", flush=True)
        print(f"  Qwen   : {qwen_out[i]}", flush=True)
        print(f"  EXAONE : {exaone_out[i]}", flush=True)
    print("\n=== 끝. 위 Qwen/EXAONE 메모 품질 비교해서 나은 쪽으로 전체 진행 ===", flush=True)


if __name__ == "__main__":
    main()
