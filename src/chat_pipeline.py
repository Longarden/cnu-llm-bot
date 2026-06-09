"""챗봇 코어 파이프라인 (Task2): 질문 → 질문유형 분류 → 분류결과 기반 RAG → 생성.

과제 흐름(PDF p4): 질문 → 질문유형 분류기(model/, label 0~4) → 그 카테고리로 RAG 검색
우선(soft routing) → EXAONE 생성. 분류기는 가벼워 CPU 추론 가능, 생성은 무거움.

label → data_category 매핑(명시, 카테고리 '리스트'):
    0 졸업요건  → [B_academic, F_department, department_general]  (전공/교양·학과별)
    1 학교공지  → [K_notices, F_department]  (학교/학과 공지)
    2 학사일정  → [B_academic]  (수강/일정)
    3 식단      → [A_dining]
    4 통학/셔틀 → [A_shuttle]
PDF상 졸업요건은 학과별 전공/교양 요건이라 학과 카테고리 포함, 공지도 학과 공지 포함.

기존 함수 재사용:
    - 분류기 추론: model/ (klue/roberta-base, AutoModelForSequenceClassification)
    - RAG+생성: interface.answer_questions._rag_answer (category_hint 로 소프트 라우팅)

환경: Python 3.10+, torch, transformers. GPU 있으면 GPU, 없으면 CPU 자동.
완전 로컬(외부 API 금지) — 생성은 generation.llm GEN_BACKEND=local(기본 EXAONE).
"""
import os
import re
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

# label(0~4) → RAG 검색 우선 카테고리(data_category) '리스트'. 과제 사양 그대로.
# 졸업요건/공지는 학과별이라 학과 카테고리(F_department, department_general)도 포함.
LABEL_TO_CATEGORY: dict[int, list[str]] = {
    0: ["B_academic", "F_department", "department_general"],  # 졸업요건 (전공/교양·학과별)
    1: ["K_notices", "F_department"],                          # 학교공지 (학교/학과)
    2: ["B_academic"],                                         # 학사일정 (수강/일정)
    3: ["A_dining"],                                           # 식단
    4: ["A_shuttle"],                                          # 통학/셔틀
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


def route_question(question: str) -> tuple[int, str, list[str]]:
    """질문 → (label, 유형명, data_category 리스트). 라우팅 결과를 한 번에 반환.

    카테고리는 '리스트'로 반환(라벨 하나가 여러 data_category 에 매핑될 수 있음).
    분류기 로드/추론 실패(모델 없음 등) 시 label=-1, categories=[] 로 폴백 →
    하류 RAG 가 전체 카테고리에서 검색(기존 동작).
    """
    try:
        label = classify(question)
    except Exception as e:
        print(f"[chat_pipeline] 분류 실패, 전체검색 폴백: {e}")
        return -1, "미분류", []
    return label, LABEL_NAMES.get(label, "?"), LABEL_TO_CATEGORY.get(label, [])


# 라이브 크롤러가 존재하는 라벨 = '라이브로 갈 때 어느 소스를 긁을지' 지도.
#   0 졸업요건·2 학사일정 → AcademicCrawler(경량 crawl_realtime), 1 공지 → Notices, 3 식단 → Dining, 4 셔틀 → Shuttle.
# 정적 vs 라이브의 '판단'은 라벨이 아니라 콘텐츠 신선도로 한다(chat_answer 참고). CHAT_REALTIME=0 이면 전부 정적.
_LIVE_CAPABLE = {0, 1, 2, 3, 4}

# 질문이 '최신/실시간'을 명시 요구하는 신호(변동·최신 키워드). + date_extractor 날짜표현 병용.
_FRESH_RE = re.compile(
    r"(최신|가장\s*최근|최근|방금|지금|현재|실시간|오늘|내일|모레|이번\s*주|다음\s*주"
    r"|새로|새롭게|바뀌|바뀐|변경|변동|업데이트|업뎃|갱신"
    r"|정상\s*운행|운행\s*여부|운행하나|운행\s*하나)"
)


def _needs_fresh(question: str) -> bool:
    """질문이 '최신/실시간' 정보를 요구하는지(변동·최신 키워드 또는 날짜표현)."""
    if _FRESH_RE.search(question):
        return True
    try:
        from retrieval.date_extractor import extract_dates
        return bool(extract_dates(question))
    except Exception:
        return False


def _static_is_stale(docs) -> bool:
    """top 검색문서가 '휘발성 정보(freshness_tier=time_sensitive: 식단·공지)'인데
    valid_until 이 오늘보다 과거(만료)면 stale → 라이브로 갱신 필요.
    안정/준안정 정보(셔틀 노선·졸업요건 등)는 변하지 않으니 그대로 신뢰(False)."""
    if not docs:
        return False
    from datetime import date
    today = date.today().isoformat()
    top = docs[0]
    meta = top.get("metadata", top) if isinstance(top, dict) else {}
    tier = meta.get("freshness_tier") or (top.get("freshness_tier", "") if isinstance(top, dict) else "")
    vu = meta.get("valid_until") or (top.get("valid_until", "") if isinstance(top, dict) else "")
    if tier == "time_sensitive" and vu:
        return str(vu) < today  # ISO 사전식 비교 = 시간순
    return False


def _try_realtime(question: str, label: int):
    """라이브 크롤 소스가 있는 라벨(공지/식단/셔틀)을 realtime 모듈로 라이브 크롤+생성.
    결과 없거나 실패면 None(→정적 폴백)."""
    if os.environ.get("CHAT_REALTIME", "1") != "1" or label not in _LIVE_CAPABLE:
        return None
    try:
        from src.realtime_model import _live_crawl, _docs_to_chunks, _generate_from_live, _CRAWL_FAIL_MSG
        docs = _live_crawl(label, question)
        if not docs:
            return None
        chunks = _docs_to_chunks(docs, question)
        if not chunks:
            return None
        ans = _generate_from_live(question, chunks)
        if not ans or ans.strip() == _CRAWL_FAIL_MSG:
            return None
        return ans
    except Exception as e:
        print(f"[chat_pipeline] 실시간 경로 실패, 정적 RAG 폴백: {e}")
        return None


def _static_answer(question: str, categories):
    """분류 카테고리로 소프트 라우팅한 정적 RAG. (답변, top_docs, 거절여부) 반환."""
    from interface.answer_questions import _rag_answer
    return _rag_answer(
        question,
        category_hint=(categories or None),  # 리스트/None — _soft_route_by_category 처리
        return_context=True,
    )


# ── 빠른 인텐트 게이트 ────────────────────────────────────────────────
# 분류기는 0~4 중 하나를 강제로 뱉으므로 인사/도메인밖/인젝션도 라벨이 붙어, 식단(3)·공지(1)로
# 오분류되면 '항상 라이브' 규칙에 걸려 불필요한 크롤로 100초 터널 한도를 넘겨 524가 난다.
# 이런 질의는 검색·크롤이 필요 없으니 RAG 앞단에서 결정론적으로 즉답해 524·지연을 원천 차단한다.
_GREETING_RE = re.compile(r"(안녕|반가|방가|하이|헬로|hello|^hi|ㅎㅇ|고마|감사|ㄱㅅ|수고|잘\s*가|뭐\s*해|뭐\s*하니|누구야|누구니|네\s*소개|자기소개|뭐\s*할\s*수|무엇을\s*할\s*수|뭐\s*가능|어떤\s*걸\s*도와|뭘\s*도와)")
_CAMPUS_RE = re.compile(r"(식단|학식|메뉴|밥|급식|셔틀|버스|정류장|배차|공지|학사|일정|졸업|학점|수강|복수전공|부전공|전과|장학|도서관|기숙사|생활관|등록|휴학|복학|시험|기말|중간|강의|캠퍼스|학생회관|푸드코트)")
_OOD_RE = re.compile(r"(다른\s*대학|타\s*대학|타대학|서울대|연세대|고려대|카이스트|한양대|성균관|경북대|부산대|날씨|주식|주가|환율|코인|비트코인|연애|여자친구|남자친구|로또|운세)")
_INJECT_RE = re.compile(r"(이전\s*지시|지시[^.]*무시|무시하고|규칙[^.]*무시|프롬프트[^.]*(무시|알려|보여|출력)|system\s*prompt|시스템\s*프롬프트|역할[^.]*무시|너의\s*지침)")

_GREETING_MSG = (
    "안녕하세요! 충남대학교 학부 재학생을 위한 안내 챗봇이에요.\n"
    "학식 메뉴, 학사일정, 학교·학과 공지, 졸업요건, 셔틀버스 같은 학내 정보를 도와드릴 수 있어요. "
    "무엇이 궁금하신가요?"
)
_OOD_MSG = (
    "충남대학교 학내 정보 범위를 벗어난 질문이에요.\n"
    "충남대 학식·학사일정·공지·졸업요건·셔틀버스 같은 학내 정보라면 도와드릴 수 있어요."
)


def _quick_intent_answer(question: str):
    """검색/크롤 없이 즉답할 질의면 (답, 유형명) 반환, 아니면 None(→ RAG 진행)."""
    q = (question or "").strip()
    if not q:
        return None
    # 인젝션 시도·도메인밖(타 대학/일반상식)은 역할 유지하며 즉답(크롤 안 함)
    if _INJECT_RE.search(q) or _OOD_RE.search(q):
        return _OOD_MSG, "도메인밖"
    # 인사·잡담: 캠퍼스 키워드가 없고 짧을 때만(예: "졸업요건 뭐야"는 campus 매칭 → 제외)
    if _GREETING_RE.search(q) and not _CAMPUS_RE.search(q) and len(q) <= 40:
        return _GREETING_MSG, "인사"
    return None


def chat_answer(question: str, return_meta: bool = False):
    """챗봇 1턴: 분류 → 정보 휘발성 판단 라우팅 → 생성.

    라이브 소스가 있는 라벨(공지1·식단3·셔틀4)에서 "변하는 정보만" 라이브로:
      · 질문이 최신 명시 요구(오늘/다음주/바뀐/정상운행 등) → 라이브 우선.
      · 평상시 → 정적 RAG 우선. 단 정적이 거절(자료없음) 이거나
        정적 top 문서가 휘발성(time_sensitive)인데 valid_until 만료(stale)면 라이브로 갱신.
      → "안 변하는 정보(freshness_tier=static·semi_static, 미만료)"는 정적 그대로 내보냄.
    라이브 소스 없는 라벨(졸업요건0·학사일정2)·미분류 → 정적 RAG.

    return_meta=True 면 (answer, {label, label_name, categories, fresh, source}) 반환.
    """
    label, label_name, categories = route_question(question)
    realtime_on = os.environ.get("CHAT_REALTIME", "1") == "1"
    # 변동정보(식단3·공지1)는 본질적으로 '오늘/최신' 데이터 → 날짜 키워드가 없어도 항상 라이브 우선.
    # (정적 RAG는 DB에 쌓인 여러 날짜를 섞어 와서 5일전·7일전이 뒤섞인 답이 나옴 → 라이브로 최신치만.)
    # 안정정보(졸업0·학사2·셔틀4)는 거의 안 변하니 정적 우선, 거절/만료 시에만 라이브 갱신.
    fresh = _needs_fresh(question) or label in (1, 3)
    source = "static"

    if realtime_on and label in _LIVE_CAPABLE and fresh:
        # 최신 요구(오늘/다음주/바뀐/최신 등) → 라이브 우선. 정적 생성을 생략해 속도↑.
        # (정적+라이브 둘 다 생성하면 생성 2회 + 리랭커 로드로 터널 100초 초과 → 524). 라이브 실패 시만 정적.
        live = _try_realtime(question, label)
        if live is not None:
            answer, source = live, "live"
        else:
            answer = _static_answer(question, categories)[0]
    else:
        # 평상시 → 정적 RAG 먼저(고정 콘텐츠 우선). 정적 거절이거나 휘발성+만료(stale)면 라이브로 갱신.
        answer, docs, rejected = _static_answer(question, categories)
        if realtime_on and (rejected or _static_is_stale(docs)):
            live = _try_realtime(question, label)
            if live is not None:
                answer, source = live, "live"

    if return_meta:
        return answer, {
            "label": label, "label_name": label_name, "categories": categories,
            "fresh": fresh, "source": source,
        }
    return answer
