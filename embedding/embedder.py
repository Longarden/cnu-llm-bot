"""BGE-M3 임베딩 모델 로드 및 인코딩."""
from typing import Optional
import numpy as np

_model = None


def get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        # use_safetensors=True 강제: 최신 transformers는 CVE-2025-32434로
        # torch<2.6에서 pytorch_model.bin 로드를 막음(bge-m3는 .bin+safetensors 둘 다 보유).
        # safetensors로 가면 torch.load를 안 거쳐 버전제한 우회.
        try:
            _model = SentenceTransformer(
                "BAAI/bge-m3", model_kwargs={"use_safetensors": True}
            )
        except TypeError:
            # 구버전 ST는 model_kwargs 미지원 → 인자 없이 로드
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
