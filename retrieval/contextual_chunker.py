"""W1 Contextual Retrieval (Anthropic 2024): 각 청크 앞에 LLM이 생성한
50~80자 컨텍스트 요약을 prepend → BM25/dense 정확도 폭증.

흐름:
  load_scoped_docs() → chunk_documents() → contextualize_chunks(llm_call)
  → 각 청크의 original_text 가 "[컨텍스트] 한 줄\\n\\n[원래 청크]" 로 갱신
  → 그 상태로 build_vector_db (임베딩 재빌드)
  → BM25 재구축 (init_bm25_from_db)

콜랩 환경:
  Qwen 3B AWQ 로딩 → wrapper llm_call(prompt: str) -> str 만들어 주입.
  2101건 × 평균 3청크 = ~6300호출. 청크당 1~2초 (T4) → 1.5~3시간.
  중간 저장(checkpoint_every) + resume 지원.

기본 청크 사이즈 400자 가정. 컨텍스트 50~80자 추가되면 청크 ~480자.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Callable, Optional

LLMCall = Callable[[str], str]

_CTX_PROMPT = """다음은 충남대학교 정보 RAG 문서의 청크입니다.

[문서 제목]
{title}

[문서 본문 앞부분]
{doc_head}

[이 청크]
{chunk}

이 청크가 위 문서 안에서 어떤 맥락(어느 절/주제/대상)인지, 검색에 도움되는 한 문장(50~80자) 요약을 한 줄로만 출력하세요. 머리말/접두어/줄바꿈 금지."""


def build_context(title: str, doc_head: str, chunk_text: str, llm_call: LLMCall) -> Optional[str]:
    """한 청크에 대한 컨텍스트 한 줄. 실패시 None."""
    try:
        prompt = _CTX_PROMPT.format(
            title=(title or "")[:120],
            doc_head=(doc_head or "")[:1500],
            chunk=(chunk_text or "")[:1200],
        )
        resp = llm_call(prompt)
    except Exception:
        return None
    if not resp:
        return None
    s = resp.strip().split("\n", 1)[0].strip(" -*[]()")
    if 10 <= len(s) <= 200:
        return s
    return None


def contextualize_chunks(docs: list[dict], chunks: list[dict], llm_call: LLMCall,
                         out_path: Optional[str] = None,
                         checkpoint_every: int = 100,
                         resume: bool = True) -> list[dict]:
    """모든 청크에 contextual prefix 추가. 중간 저장 + resume 지원.

    Args:
      docs: 원본 문서 리스트 (load_scoped_docs 결과)
      chunks: 청킹 결과 리스트 (chunk_documents 결과)
      llm_call: prompt → response 콜백 (콜랩 Qwen wrapper)
      out_path: 저장 경로 (None이면 메모리만)
      checkpoint_every: N개마다 디스크 저장
      resume: True면 out_path 존재 시 거기서부터 이어함
    """
    # url+청크인덱스로 doc 매핑 (chunker가 doc 내 청크 순서대로 만든다 가정)
    doc_map = {}
    for d in docs:
        doc_map[d.get("source_url", "")] = d

    # resume
    done = []
    start = 0
    if resume and out_path and os.path.exists(out_path):
        try:
            done = json.load(open(out_path, encoding="utf-8"))
            start = len(done)
            print(f"[contextual] resume from {start}/{len(chunks)}")
        except Exception:
            done = []
            start = 0

    out = list(done)
    ok_count = sum(1 for x in out if x.get("context_prefix"))

    for i in range(start, len(chunks)):
        ch = chunks[i]
        url = ch.get("source_url", "") or ""
        d = doc_map.get(url, {})
        title = d.get("title", "")
        doc_head = d.get("original_text", "") or d.get("content", "")
        chunk_text = ch.get("original_text", "") or ch.get("text", "")
        ctx = build_context(title, doc_head, chunk_text, llm_call)
        new_ch = dict(ch)
        if ctx:
            new_ch["context_prefix"] = ctx
            new_ch["original_text"] = f"{ctx}\n\n{chunk_text}"
            new_ch["content"] = new_ch["original_text"]
            ok_count += 1
        out.append(new_ch)

        if (i + 1) % checkpoint_every == 0:
            print(f"  진행 {i+1}/{len(chunks)}  컨텍스트 생성 {ok_count}", flush=True)
            if out_path:
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(out, f, ensure_ascii=False, indent=2)

    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"[contextual] 완료. 총 {len(out)} 청크, 컨텍스트 성공 {ok_count}")
    return out


# ------------------- 콜랩에서 호출용 예시 -------------------

COLAB_USAGE = '''
콜랩에서 사용 예시:

# 1) Qwen 3B 로딩
from transformers import AutoTokenizer
from awq import AutoAWQForCausalLM
model_id = "Qwen/Qwen2.5-3B-Instruct-AWQ"
tok = AutoTokenizer.from_pretrained(model_id)
model = AutoAWQForCausalLM.from_quantized(model_id, fuse_layers=True, device_map="cuda")
def llm_call(prompt: str) -> str:
    msgs = [{"role":"user","content":prompt}]
    inputs = tok.apply_chat_template(msgs, tokenize=True, add_generation_prompt=True, return_tensors="pt").to("cuda")
    out = model.generate(inputs, max_new_tokens=120, do_sample=False, pad_token_id=tok.pad_token_id or tok.eos_token_id)
    return tok.decode(out[0][inputs.shape[1]:], skip_special_tokens=True)

# 2) 컨텍스트 생성
from embedding.data_loader import load_scoped_docs
from embedding.chunker import chunk_documents
from retrieval.contextual_chunker import contextualize_chunks
docs = load_scoped_docs()
chunks = chunk_documents(docs)
ctx_chunks = contextualize_chunks(
    docs, chunks, llm_call,
    out_path="data/contextual_chunks.json",
    checkpoint_every=100,
    resume=True,
)

# 3) 벡터DB 재빌드 (contextual prefix 포함된 chunks 로)
from embedding.vector_store import build_vector_db, CHROMA_PATH
import chromadb
client = chromadb.PersistentClient(path=CHROMA_PATH)
try: client.delete_collection("cnu_rag")
except: pass
build_vector_db(ctx_chunks)
'''


if __name__ == "__main__":
    print("이 모듈은 콜랩에서 LLM 주입 후 호출.")
    print(COLAB_USAGE)
