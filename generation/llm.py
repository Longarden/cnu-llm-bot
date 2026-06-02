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

# 환경변수로 모델 지정 가능. 결정(2026-06-02): 답변생성=EXAONE-3.5-2.4B-Instruct + bitsandbytes 4bit.
# 이유: EXAONE은 한국어 네이티브라 중국어 코드스위칭이 없음(Qwen의 유일한 약점 해소).
#   단 EXAONE 최신 remote code는 transformers 4.49+(RopeParameters)를 요구해 4.48(torch2.5.1 조건)에서
#   깨지므로, RopeParameters 이전 '초기 릴리스 리비전'을 핀해서 4.48에서 로드(가중치는 최신과 동일,
#   config만 옛 버전). 2.4B는 검증 완료(16문항 한국어 정상). 7.8B는 MODEL_PRIMARY_NAME 으로 업그레이드.
MODEL_PRIMARY = os.environ.get("MODEL_PRIMARY_NAME",
                               "LGAI-EXAONE/EXAONE-3.5-2.4B-Instruct")
MODEL_EXAONE_78B_AWQ = "LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct-AWQ"  # 참고용(torch>=2.6 환경 전용)
MODEL_FALLBACK = os.environ.get("MODEL_FALLBACK_NAME", "Qwen/Qwen2.5-7B-Instruct")

# EXAONE 안전 리비전(2024-12-09 초기 릴리스, RopeParameters 추가 전). MODEL_REVISION 미지정 시 자동 적용.
EXAONE_SAFE_REVISIONS = {
    "LGAI-EXAONE/EXAONE-3.5-2.4B-Instruct": "8e6fc27",
    "LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct": "496aef0",
}

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
        # MODEL_REVISION: 특정 커밋 고정용. EXAONE처럼 최신 remote code가 transformers 4.49+를
        # 요구해 깨질 때, RopeParameters 이전 옛 리비전(예: EXAONE-3.5-2.4B 8e6fc27, 2024-12-09)을
        # 박으면 transformers 4.48(torch 2.5.1 조건)에서도 로드 가능.
        revision = os.environ.get("MODEL_REVISION", "").strip() or EXAONE_SAFE_REVISIONS.get(name)
        tokenizer = AutoTokenizer.from_pretrained(name, trust_remote_code=True, revision=revision)
        device_map = "auto" if torch.cuda.is_available() else "cpu"
        load_kwargs = dict(
            device_map=device_map,
            trust_remote_code=True,
            revision=revision,
            use_safetensors=True,  # torch<2.6 .bin 차단(CVE-2025-32434) 우회
        )
        is_awq = "awq" in name.lower()
        # 비-AWQ 모델은 bitsandbytes 4bit로 로드(T4에 7B ~5GB). AWQ(autoawq)는
        # transformers 4.51을 기대해 4.48에서 qwen3 import로 깨지므로, 표준 모델 +
        # bitsandbytes 4bit가 torch 2.5.1/transformers 4.48에서 가장 안정적.
        if not is_awq and torch.cuda.is_available():
            try:
                from transformers import BitsAndBytesConfig
                load_kwargs["quantization_config"] = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_quant_type="nf4",
                    bnb_4bit_compute_dtype=torch.float16,
                    bnb_4bit_use_double_quant=True,
                )
            except Exception as e:
                logger.warning(f"bitsandbytes 4bit 구성 실패, 기본 로드: {e}")
        try:
            model = AutoModelForCausalLM.from_pretrained(name, **load_kwargs)
        except (ValueError, OSError):
            load_kwargs.pop("use_safetensors", None)
            model = AutoModelForCausalLM.from_pretrained(name, **load_kwargs)
        pipe = pipeline(
            "text-generation",
            model=model,
            tokenizer=tokenizer,
            max_new_tokens=512,
            do_sample=False,
            repetition_penalty=1.05,
        )
        return pipe

    # 1차 시도. 메모리부족 신호는 torch.cuda.OutOfMemoryError(타입) 외에도
    # accelerate device_map 산정 실패("won't fit"/"dispatched on the CPU") 등
    # 문자열만 다른 경우가 있어 타입+다중 문자열로 폭넓게 감지해 3B로 폴백.
    _OOM_HINTS = ("out of memory", "won't fit", "wont fit", "cuda error",
                  "not enough", "dispatched on the cpu", "no available memory")
    try:
        _llm_pipeline = _build_pipeline(target_model)
    except Exception as e:
        is_oom = isinstance(e, getattr(torch.cuda, "OutOfMemoryError", tuple())) \
            or any(h in str(e).lower() for h in _OOM_HINTS)
        if is_oom and fallback_mode != "0" and target_model != MODEL_FALLBACK:
            logger.warning(f"메모리부족 추정({target_model}: {e}). {MODEL_FALLBACK}로 폴백.")
            _llm_pipeline = _build_pipeline(MODEL_FALLBACK)
        else:
            raise

    logger.info("LLM 로드 완료.")
    return _llm_pipeline


# ── 생성 백엔드 선택 ──────────────────────────────────────────────
# GEN_BACKEND=api(기본) → Gemini API 우선, 실패/키없음 시 로컬 폴백.
# GEN_BACKEND=local      → 로컬 EXAONE/Qwen 강제(자작 모델 검증·오프라인용).
# 과제 PDF: 서버 아키텍처라 외부 API 허용. 성능 우선 = API Pro 기본.
GEN_BACKEND = os.environ.get("GEN_BACKEND", "local").lower()
GEMINI_GEN_MODEL = os.environ.get("GEMINI_GEN_MODEL", "gemini-2.5-pro")    # 답변
GEMINI_FAST_MODEL = os.environ.get("GEMINI_FAST_MODEL", "gemini-2.5-flash")  # 쿼리변환/검증

_gemini_client = None


def _get_gemini():
    """google-genai 클라이언트 싱글턴. 키 없으면 None."""
    global _gemini_client
    if _gemini_client is not None:
        return _gemini_client
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        return None
    try:
        from google import genai
        _gemini_client = genai.Client(api_key=key)
    except Exception as e:
        logger.warning(f"Gemini 클라이언트 초기화 실패: {e}")
        return None
    return _gemini_client


def _gemini_generate(prompt: str, system_prompt: str, model: str) -> str:
    """Gemini API 생성. 실패 시 예외(상위에서 로컬 폴백)."""
    client = _get_gemini()
    if client is None:
        raise RuntimeError("GEMINI_API_KEY 없음")
    from google.genai import types
    cfg = types.GenerateContentConfig(
        system_instruction=system_prompt or None,
        temperature=0.0,
        max_output_tokens=1024,
    )
    resp = client.models.generate_content(model=model, contents=prompt, config=cfg)
    return (resp.text or "").strip()


def _local_generate(prompt: str, system_prompt: str = "") -> str:
    """로컬 파이프라인(EXAONE/Qwen) 생성. chat template 적용."""
    pipe = load_llm()
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    outputs = pipe(messages)
    if isinstance(outputs, list) and outputs:
        generated = outputs[0]
        if isinstance(generated, dict):
            text = generated.get("generated_text", "")
            if isinstance(text, list):
                for msg in reversed(text):
                    if isinstance(msg, dict) and msg.get("role") == "assistant":
                        return msg.get("content", "").strip()
            return str(text).strip()
    return ""


import re as _re_cjk
_CJK_RE = _re_cjk.compile(r"[一-鿿]")


def _has_chinese(text: str) -> bool:
    """한자(중국어)가 2자 이상이면 코드스위칭 의심."""
    return len(_CJK_RE.findall(text or "")) >= 2


def _generate_once(prompt: str, system_prompt: str = "") -> str:
    """1회 생성. GEN_BACKEND=api면 Gemini Pro 우선, 실패 시 로컬 폴백."""
    if GEN_BACKEND == "api":
        try:
            out = _gemini_generate(prompt, system_prompt, GEMINI_GEN_MODEL)
            if out:
                return out
            logger.warning("Gemini 빈 응답 → 로컬 폴백")
        except Exception as e:
            logger.warning(f"Gemini 생성 실패({e}) → 로컬 폴백")
    return _local_generate(prompt, system_prompt)


def generate(prompt: str, system_prompt: str = "") -> str:
    """답변 생성 + 중국어 누출 시 한국어로 1회 재생성.

    Qwen 등이 가끔 중국어로 코드스위칭하는데, 그 줄을 '삭제'하면 거기에만 있던
    정보가 손실될 수 있다. 그래서 중국어가 감지되면 같은 컨텍스트로 '한국어로만'
    다시 생성해 정보를 보존한다(삭제는 최종 안전망으로 _clean_answer가 담당).
    """
    out = _generate_once(prompt, system_prompt)
    if _has_chinese(out):
        logger.info("중국어 누출 감지 → 한국어 재생성 시도")
        ko_sys = (system_prompt +
                  "\n\n[중요] 직전 답변에 중국어가 섞였습니다. 절대 중국어를 쓰지 말고, "
                  "동일한 정보를 빠짐없이 반드시 한국어로만 다시 작성하십시오.").strip()
        retry = _generate_once(prompt, ko_sys)
        if retry and not _has_chinese(retry):
            return retry
    return out


def generate_fast(prompt: str, system_prompt: str = "") -> str:
    """보조 생성(쿼리변환·근거검증 등). Gemini Flash 우선, 실패 시 로컬 폴백."""
    if GEN_BACKEND == "api":
        try:
            out = _gemini_generate(prompt, system_prompt, GEMINI_FAST_MODEL)
            if out:
                return out
        except Exception as e:
            logger.warning(f"Gemini Flash 실패({e}) → 로컬 폴백")
    return _local_generate(prompt, system_prompt)


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
