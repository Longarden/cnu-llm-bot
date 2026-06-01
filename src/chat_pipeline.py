"""챗봇 코어 파이프라인 (Task2): 질문 → 질문유형 분류 → 분류결과 기반 RAG → 생성.

과제 흐름(PDF p4): 질문 → 질문유형 분류기(model/, label 0~4) → 그 카테고리로 RAG 검색
우선(soft routing) → EXAONE 생성. 분류기는 가벼워 CPU 추론 가능, 생성은 무거움.

label → data_category 매핑(명시):
    0 졸업요건  → B_academic   (졸업/학점/요건)
    1 학교공지  → K_notices
    2 학사일정  → B_academic   (수강/일정)
    3 식단      → A_dining
    4 통학/셔틀 → A_shuttle

기존 함수 재사용:
    - 분류기 추론: model/ (klue/bert-base, AutoModelForSequenceClassification)
    - RAG+생성: interface.answer_questions._rag_answer (category_hint 로 소프트 라우팅)

환경: Python 3.10+, torch, transformers. GPU 있으면 GPU, 없으면 CPU 자동.
완전 로컬(외부 API 금지) — 생성은 generation.llm GEN_BACKEND=local(기본 EXAONE).
"""
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path 에 추가(어디서 실행하든 import 되도록)
try:
    ROOT = Path(__file__).resolve().parent.parent
except NameError:  # 노트북 등 __file__ 없는 환경
    ROOT = Path.cwd()
    if not (ROOT / "interface").exists() and (ROOT.parent / "interface").exists():
        ROOT = ROOT.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

MODEL_DIR = ROOT / "model"
MAX_LEN = 64

# label(0~4) → RAG 검색 우선 카테고리(data_category). 과제 사양 그대로.
LABEL_TO_CATEGORY: dict[int, str] = {
    0: "B_academic",  # 졸업요건 (졸업/학점/요건)
    1: "K_notices",   # 학교공지
    2: "B_academic",  # 학사일정 (수강/일정)
    3: "A_dining",    # 식단
    4: "A_shuttle",   # 통학/셔틀
}

# label → 사람이 읽는 유형명(로그/디버그용). model/label_map.json 과 동일.
LABEL_NAMES: dict[int, str] = {
    0: "졸업요건",
    1: "학교공지",
    2: "학사일정",
    3: "식단",
    4: "통학/셔틀",
}

# 분류기 싱글턴 캐시(tokenizer, model)
_classifier = None


def load_classifier():
    """분류기(tokenizer, model) 싱글턴 로드. model/ 에서 로컬 로드."""
    global _classifier
    if _classifier is not None:
        return _classifier
    import torch
    from transformers import AutoTokenizer, AutoModelForSequenceClassification

    device = "cuda" if torch.cuda.is_available() else "cpu"
    tokenizer = AutoTokenizer.from_pretrained(str(MODEL_DIR))
    model = AutoModelForSequenceClassification.from_pretrained(str(MODEL_DIR))
    model.to(device)
    model.eval()
    _classifier = (tokenizer, model, device)
    return _classifier


def classify(question: str) -> int:
    """질문 → 질문유형 label(0~4) 예측."""
    import torch

    tokenizer, model, device = load_classifier()
    enc = tokenizer(
        [question], truncation=True, max_length=MAX_LEN,
        padding=True, return_tensors="pt",
    ).to(device)
    with torch.no_grad():
        logits = model(**enc).logits
    return int(logits.argmax(dim=-1).cpu().item())


def route_question(question: str) -> tuple[int, str, str]:
    """질문 → (label, 유형명, data_category). 라우팅 결과를 한 번에 반환.

    분류기 로드/추론 실패(모델 없음 등) 시 label=-1, category="" 로 폴백 →
    하류 RAG 가 전체 카테고리에서 검색(기존 동작).
    """
    try:
        label = classify(question)
    except Exception as e:
        print(f"[chat_pipeline] 분류 실패, 전체검색 폴백: {e}")
        return -1, "미분류", ""
    return label, LABEL_NAMES.get(label, "?"), LABEL_TO_CATEGORY.get(label, "")


def chat_answer(question: str, return_meta: bool = False):
    """챗봇 1턴: 분류 → 소프트 라우팅 RAG → 생성. 최종 답변 문자열 반환.

    return_meta=True 면 (answer, {"label","label_name","category"}) 튜플 반환.
    """
    label, label_name, category = route_question(question)

    from interface.answer_questions import _rag_answer
    answer = _rag_answer(
        question,
        category_hint=(category or None),
    )

    if return_meta:
        return answer, {"label": label, "label_name": label_name, "category": category}
    return answer
