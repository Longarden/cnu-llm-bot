"""P100 — 계층적 Contextual prefix (2-pass).

1단계: 문서(2056개)마다 전체 요약 doc_summary 생성 (문서 앞 DOC_CAP자 → 200자 요약)
2단계: 청크 메모 = [doc_summary] + [청크] → 한 줄 메모 (긴 문서 맥락을 요약으로 압축 참조)

doc_head(앞 600자 잘림) 방식보다 긴 학칙·규정에서 메모 품질↑.
7B FP16 (GPU4 16GB). 양자화 안 함 → cublasLt 문제 無.

실행:
  export CUDA_VISIBLE_DEVICES=4 CTX_MODEL=Qwen/Qwen2.5-7B-Instruct CTX_BATCH=4
  export CTX_OUT=data/contextual_chunks_7b.json
  nohup python -u scripts/run_contextual_hier_p100.py > data/planner/ctx_hier_7b.log 2>&1 &

각 단계 resume 지원 (doc_summaries.json / contextual_chunks_7b.json).
"""
import sys, os, json, time, math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

from embedding.data_loader import load_scoped_docs
from embedding.chunker import chunk_documents

MODEL = os.environ.get("CTX_MODEL", "Qwen/Qwen2.5-7B-Instruct")
OUT = os.environ.get("CTX_OUT", str(ROOT / "data" / "contextual_chunks_7b.json"))
SUM_OUT = str(ROOT / "data" / "doc_summaries.json")
BATCH = int(os.environ.get("CTX_BATCH", "4"))
DOC_CAP = int(os.environ.get("HIER_DOC_CAP", "4000"))   # 문서 요약에 넣을 앞부분 길이
CHUNK_CAP = int(os.environ.get("CTX_CHUNK_CAP", "700"))

SUM_PROMPT = """다음은 충남대학교 정보 문서입니다. 이 문서가 전체적으로 무엇에 관한 것인지(주제·대상·핵심 내용) 검색 맥락용으로 200자 이내 한 단락으로 요약하세요. 목록·머리말 없이 요약문만 출력.

[문서]
{doc}

[요약]"""

HIER_PROMPT = """다음은 충남대학교 RAG 문서의 한 청크입니다.

[문서 전체 요약]
{summary}

[이 청크]
{chunk}

이 청크가 위 문서에서 어떤 맥락(어느 절/주제/대상)인지, 검색에 도움되는 한 문장(50~80자) 요약을 한 줄로만 출력하세요. 머리말/접두어/줄바꿈 금지."""


def clean_one(s, lo=10, hi=200):
    s = (s or "").strip().split("\n", 1)[0].strip(" -*[]()\t")
    return s if lo <= len(s) <= hi else ""


def main():
    print("=== P100 계층적 contextual (2-pass) ===", flush=True)
    print(f"  model={MODEL}  BATCH={BATCH}  DOC_CAP={DOC_CAP}", flush=True)
    print(f"  device={torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'cpu'}", flush=True)

    t0 = time.time()
    tok = AutoTokenizer.from_pretrained(MODEL)
    tok.padding_side = "left"
    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(MODEL, torch_dtype=torch.float16).to("cuda")
    model.eval()
    pad = tok.pad_token_id
    print(f"  모델 로딩 {time.time()-t0:.0f}s", flush=True)

    @torch.no_grad()
    def gen_batch(prompts, max_new):
        texts = [tok.apply_chat_template([{"role": "user", "content": p}],
                                         tokenize=False, add_generation_prompt=True) for p in prompts]
        enc = tok(texts, return_tensors="pt", padding=True, truncation=True, max_length=8192).to("cuda")
        g = model.generate(**enc, max_new_tokens=max_new, do_sample=False, pad_token_id=pad)
        new = g[:, enc["input_ids"].shape[1]:]
        return [t.strip() for t in tok.batch_decode(new, skip_special_tokens=True)]

    docs = load_scoped_docs()
    print(f"  문서 {len(docs)}개", flush=True)

    # ── 1단계: 문서 요약 ──
    summaries = {}
    if os.path.exists(SUM_OUT):
        try:
            summaries = json.load(open(SUM_OUT, encoding="utf-8"))
            print(f"  [1단계] resume: {len(summaries)} 요약 완료", flush=True)
        except Exception:
            summaries = {}
    todo = [d for d in docs if (d.get("source_url", "") or "") not in summaries]
    print(f"  [1단계] 요약할 문서 {len(todo)}개", flush=True)
    t1 = time.time()
    for i in range(0, len(todo), BATCH):
        batch = todo[i:i + BATCH]
        prompts = [SUM_PROMPT.format(doc=(d.get("original_text", "") or "")[:DOC_CAP]) for d in batch]
        outs = gen_batch(prompts, 256)
        for d, o in zip(batch, outs):
            summaries[d.get("source_url", "")] = clean_one(o, 10, 400) or o.strip()[:300]
        if (i // BATCH) % 20 == 0 or i + BATCH >= len(todo):
            done = len([1 for _ in summaries])
            el = time.time() - t1
            print(f"    요약 {min(i+BATCH,len(todo))}/{len(todo)}  {el/60:.0f}분 경과", flush=True)
            json.dump(summaries, open(SUM_OUT, "w", encoding="utf-8"), ensure_ascii=False)
    json.dump(summaries, open(SUM_OUT, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"  [1단계] 완료. 요약 {len(summaries)}개", flush=True)

    # ── 2단계: 청크 메모 (요약 참조) ──
    chunks = chunk_documents(docs)
    print(f"  [2단계] 청크 {len(chunks)}개", flush=True)
    out_list = []
    if os.path.exists(OUT):
        try:
            out_list = json.load(open(OUT, encoding="utf-8"))
            print(f"  [2단계] resume: {len(out_list)}/{len(chunks)}", flush=True)
        except Exception:
            out_list = []
    start = len(out_list)
    ok = sum(1 for x in out_list if x.get("context_prefix"))
    t2 = time.time()
    for i in range(start, len(chunks), BATCH):
        batch = chunks[i:i + BATCH]
        prompts = [HIER_PROMPT.format(
            summary=summaries.get(c.get("source_url", ""), "")[:300],
            chunk=(c.get("original_text", "") or "")[:CHUNK_CAP],
        ) for c in batch]
        outs = gen_batch(prompts, 80)
        for c, raw in zip(batch, outs):
            prefix = clean_one(raw)
            nc = dict(c)
            if prefix:
                ctext = c.get("original_text", "") or ""
                nc["context_prefix"] = prefix
                nc["original_text"] = f"{prefix}\n\n{ctext}"
                nc["content"] = nc["original_text"]
                ok += 1
            out_list.append(nc)
        if (i // BATCH) % 20 == 0 or i + BATCH >= len(chunks):
            done = len(out_list)
            el = time.time() - t2
            rate = (done - start) / max(el, 1)
            eta = (len(chunks) - done) / max(rate, 1e-6)
            print(f"    메모 {done}/{len(chunks)}  prefix={ok}  {rate:.2f}청크/s  ETA {eta/60:.0f}분", flush=True)
            json.dump(out_list, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    json.dump(out_list, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n=== 완료 ===  prefix {ok}/{len(out_list)}  → {OUT}", flush=True)


if __name__ == "__main__":
    main()
