"""BGE-M3 임베딩 모델 로드 및 인코딩."""
from typing import Optional
import numpy as np

_model = None


def get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        # bge-m3는 pytorch_model.bin만 배포(safetensors 없음). transformers<4.49 고정으로
        # torch 2.5.1에서도 .bin 로드 허용(>=4.49는 CVE-2025-32434로 .bin 차단). requirements 참고.
        _model = SentenceTransformer("BAAI/bge-m3")
    return _model


def encode(texts: list[str], batch_size: int = 32) -> np.ndarray:
    model = get_model()
    return model.encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=True,
    )
