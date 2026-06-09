"""BGE-M3 임베딩 모델 로드 및 인코딩."""
from typing import Optional
import numpy as np

_model = None


def get_model():
    global _model
    if _model is None:
        import os
        from sentence_transformers import SentenceTransformer
        # bge-m3는 pytorch_model.bin만 배포(safetensors 없음). transformers<4.49 고정으로
        # torch 2.5.1에서도 .bin 로드 허용(>=4.49는 CVE-2025-32434로 .bin 차단). requirements 참고.
        # EMBED_DEVICE=cpu 면 임베더를 CPU로(7.8B 생성에 VRAM 양보). 미지정=자동(GPU 있으면 GPU).
        device = os.environ.get("EMBED_DEVICE") or None
        _model = SentenceTransformer("BAAI/bge-m3", device=device)
    return _model


def encode(texts: list[str], batch_size: int = 32, show_progress_bar: bool = False) -> np.ndarray:
    # 단건 질문 인코딩(검색 경로)에서는 진행바가 순수 오버헤드 → 기본 False.
    # 대량 색인(build_vector_db)에서만 show_progress_bar=True 로 호출해 진행상황 표시.
    model = get_model()
    return model.encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=show_progress_bar,
    )
