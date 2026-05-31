"""
답변생성 LLM 로드 모듈.
PRIMARY: EXAONE-3.5-7.8B-Instruct-AWQ (한국어 특화, W4A16, T4=compute7.5에서 정상).
         transformers>=4.43, autoawq>=0.2.7.post3 필요 (현 pin 4.44.2 충족).
T4 OOM 시 Qwen2.5-3B-Instruct 로 자동 폴백.
GPU 없는 환경(iGPU/CPU)에서 import만 성공하고 실제 로드는 코랩에서.

환경변수:
  MODEL_PRIMARY_NAME   기본 답변모델 override (기본 EXAONE AWQ)
  MODEL_FALLBACK_NAME  폴백모델 override (기본 Qwen 3B)
  MODEL_FALLBACK=auto  PRIMARY 로드, OOM 시 폴백 (T4 기본 권장)
  MODEL_FALLBACK=3b    폴백모델로 강제 (저사양 GPU)
  MODEL_FALLBACK=0     폴백 비활성화 (OOM 시 예외)
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# 환경변수로 모델 지정 가능. PRIMARY=EXAONE(한국어 특화), Qwen 7B AWQ는 대안.
MODEL_PRIMARY = os.environ.get("MODEL_PRIMARY_NAME",
                               "LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct-AWQ")
MODEL_QWEN_AWQ = "Qwen/Qwen2.5-7B-Instruct-AWQ"  # A/B 대조군
MODEL_FALLBACK = os.environ.get("MODEL_FALLBACK_NAME", "Qwen/Qwen2.5-3B-Instruct")

_llm_pipeline = None


def load_llm(model_name: Optional[str] = None) -> object:
    """
    LLM 파이프라인 로드. 싱글턴 캐싱.

    환경변수:
        MODEL_FALLBACK=3b  → 3B 모델로 강제 폴백
        MODEL_FALLBACK=0   → 폴백 비활성화 (OOM 시 예외 발생)
    """
    global _llm_pipeline
    if _llm_pipeline is not None:
        return _llm_pipeline

    # 지연 임포트: GPU 없는 노트북에서 import 단계 실패 방지
    try:
        import torch
        from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
    except ImportError as e:
        raise ImportError(f"transformers / torch 설치 필요: {e}")

    # 기본 auto: PRIMARY(EXAONE AWQ) 로드 후 OOM 시에만 3B 폴백 (T4 권장).
    fallback_mode = os.environ.get("MODEL_FALLBACK", "auto").lower()

    # 강제 폴백 모드
    if fallback_mode == "3b":
        target_model = MODEL_FALLBACK
    elif fallback_mode == "0":
        target_model = model_name or MODEL_PRIMARY
    else:
        target_model = model_name or MODEL_PRIMARY

    def _build_pipeline(name: str) -> object:
        logger.info(f"LLM 로드 중: {name}")
        tokenizer = AutoTokenizer.from_pretrained(name, trust_remote_code=True)
        device_map = "auto" if torch.cuda.is_available() else "cpu"
        # AWQ 모델은 AutoAWQ가 transformers와 연동 — 4bit 자동 처리
        model = AutoModelForCausalLM.from_pretrained(
            name,
            device_map=device_map,
            trust_remote_code=True,
        )
        pipe = pipeline(
            "text-generation",
            model=model,
            tokenizer=tokenizer,
            max_new_tokens=512,
            do_sample=False,
            temperature=None,
            top_p=None,
            repetition_penalty=1.05,
        )
        return pipe

    # 1차 시도
    try:
        _llm_pipeline = _build_pipeline(target_model)
    except (RuntimeError, Exception) as e:
        if "out of memory" in str(e).lower() and fallback_mode != "0":
            logger.warning(f"OOM 발생 ({target_model}). 3B 모델로 폴백.")
            _llm_pipeline = _build_pipeline(MODEL_FALLBACK)
        else:
            raise

    logger.info("LLM 로드 완료.")
    return _llm_pipeline


def generate(prompt: str, system_prompt: str = "") -> str:
    """
    단일 프롬프트로 텍스트 생성.
    messages 형식으로 chat template 적용.
    """
    pipe = load_llm()
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    # pipeline이 chat template를 지원하는지 확인
    try:
        outputs = pipe(messages)
        # transformers pipeline chat 출력 형식
        if isinstance(outputs, list) and outputs:
            generated = outputs[0]
            if isinstance(generated, dict):
                # [{"generated_text": [...]}] 형식
                text = generated.get("generated_text", "")
                if isinstance(text, list):
                    # 마지막 assistant 메시지 추출
                    for msg in reversed(text):
                        if isinstance(msg, dict) and msg.get("role") == "assistant":
                            return msg.get("content", "").strip()
                return str(text).strip()
    except Exception as e:
        logger.error(f"생성 오류: {e}")
        raise

    return ""


def print_gpu_memory():
    """현재 GPU 메모리 사용량 출력 (코랩 모니터링용)."""
    try:
        import torch
        if torch.cuda.is_available():
            allocated = torch.cuda.memory_allocated() / 1024**3
            reserved = torch.cuda.memory_reserved() / 1024**3
            total = torch.cuda.get_device_properties(0).total_memory / 1024**3
            print(f"GPU 메모리: {allocated:.2f}GB 사용 / {reserved:.2f}GB 예약 / {total:.2f}GB 전체")
        else:
            print("GPU 없음 (CPU 모드)")
    except ImportError:
        print("torch 미설치 — GPU 메모리 확인 불가")
