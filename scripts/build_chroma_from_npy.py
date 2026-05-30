"""콜랩(또는 어디서나) — P100이 만든 embeddings.npy + chunks_meta.json → chroma DB 조립.

임베딩 재계산 0. 미리 만든 벡터를 chroma에 넣기만 함 (빌드/서빙 분리의 서빙쪽).

실행 (콜랩):
  python scripts/build_chroma_from_npy.py
출력: chroma_db/ (cnu_rag 컬렉션) + BM25는 검색 시 자동 구축
"""
import sys, os, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np
from embedding.vector_store import CHROMA_PATH

EMB = str(ROOT / "data" / "embeddings.npy")
META = str(ROOT / "data" / "chunks_meta.json")
BATCH = 2000


def main():
    for p in (EMB, META):
        if not os.path.exists(p):
            print(f"[에러] {p} 없음. P100서 run_embed_p100.py 먼저 돌리고 전송해야 함.")
            sys.exit(1)

    embs = np.load(EMB)
    meta = json.load(open(META, encoding="utf-8"))
    print(f"임베딩 {embs.shape}  메타 {len(meta)}건")
    assert len(meta) == embs.shape[0], "임베딩 수 != 메타 수 (전송 불일치)"

    import chromadb
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    try:
        client.delete_collection("cnu_rag")
        print("기존 컬렉션 삭제")
    except Exception as e:
        print(f"삭제 스킵: {e}")
    col = client.get_or_create_collection("cnu_rag", metadata={"hnsw:space": "cosine"})

    for i in range(0, len(meta), BATCH):
        j = min(i + BATCH, len(meta))
        col.add(
            embeddings=embs[i:j].tolist(),
            documents=[m.get("original_text", "") for m in meta[i:j]],
            metadatas=[m for m in meta[i:j]],
            ids=[f"doc_{k}" for k in range(i, j)],
        )
        print(f"  {j}/{len(meta)} 저장", flush=True)

    print(f"\n=== 완료. chroma cnu_rag 청크수: {col.count()} ===")
    print("  이제 검색·답변(B부) 작동. answer_questions 실행 가능.")


if __name__ == "__main__":
    main()
