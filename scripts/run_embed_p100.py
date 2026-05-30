"""P100 서버 전용 — ⑤ 임베딩 빌드 (메모 ④ 끝난 뒤 실행).

contextual_chunks.json(메모 붙은 청크) → bge-m3 임베딩 → embeddings.npy + chunks_meta.json.
콜랩은 이 둘을 받아 chroma.add 만 하면 됨 (임베딩 재계산 0 = 빌드/서빙 분리).

bge-m3는 560M 작은 모델 + 양자화 안 함 → P100 FP16서 cublasLt 문제 없이 빠름.

실행:
  export CUDA_VISIBLE_DEVICES=0
  pip install -q sentence-transformers
  cd /workspace/cnu-llm-bot
  python scripts/run_embed_p100.py
출력: data/embeddings.npy  +  data/chunks_meta.json
"""
import sys, os, json, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np

CTX = os.environ.get("CTX_OUT", str(ROOT / "data" / "contextual_chunks.json"))
EMB_OUT = str(ROOT / "data" / "embeddings.npy")
META_OUT = str(ROOT / "data" / "chunks_meta.json")
BATCH = int(os.environ.get("EMB_BATCH", "64"))

# 콜랩 chroma.add에 넣을 메타 6종 (vector_store.REQUIRED_METADATA와 동일)
REQUIRED = ["source_url", "data_category", "last_crawled_at",
            "valid_until", "freshness_tier", "original_text"]


def main():
    print("=== P100 임베딩 빌드 (bge-m3) ===", flush=True)
    if not os.path.exists(CTX):
        print(f"  [에러] {CTX} 없음. 메모(④) 먼저 끝내야 함.", flush=True)
        sys.exit(1)
    chunks = json.load(open(CTX, encoding="utf-8"))
    print(f"  청크 {len(chunks)}개 로드", flush=True)

    # 빈 텍스트 제외
    items = [(c, (c.get("original_text", "") or "").strip()) for c in chunks]
    items = [(c, t) for c, t in items if t]
    texts = [t for _, t in items]
    print(f"  유효 텍스트 {len(texts)}개 (빈 것 제외)", flush=True)

    import torch
    from sentence_transformers import SentenceTransformer
    print(f"  torch {torch.__version__}  cuda={torch.cuda.is_available()}", flush=True)
    if torch.cuda.is_available():
        print(f"  device: {torch.cuda.get_device_name(0)}", flush=True)

    t0 = time.time()
    model = SentenceTransformer("BAAI/bge-m3")  # 자동으로 cuda 사용
    print(f"  모델 로딩 {time.time()-t0:.0f}s", flush=True)

    t1 = time.time()
    embs = model.encode(
        texts, batch_size=BATCH,
        normalize_embeddings=True, show_progress_bar=True,
    )
    embs = np.asarray(embs, dtype=np.float32)
    dt = time.time() - t1
    print(f"  임베딩 완료 {embs.shape}  {dt/60:.1f}분 ({len(texts)/max(dt,1):.0f}건/s)", flush=True)

    np.save(EMB_OUT, embs)
    meta = [{k: str(c.get(k, "")) for k in REQUIRED} for c, _ in items]
    json.dump(meta, open(META_OUT, "w", encoding="utf-8"), ensure_ascii=False)

    sz_npy = os.path.getsize(EMB_OUT) / 1024 / 1024
    sz_meta = os.path.getsize(META_OUT) / 1024 / 1024
    print(f"\n=== 완료 ===", flush=True)
    print(f"  {EMB_OUT}  ({sz_npy:.0f} MB, shape {embs.shape})", flush=True)
    print(f"  {META_OUT}  ({sz_meta:.0f} MB, {len(meta)}건)", flush=True)
    print(f"  → 이 둘을 콜랩으로 옮겨 chroma.add 만 하면 끝", flush=True)


if __name__ == "__main__":
    main()
