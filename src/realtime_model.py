"""Task3 실시간반영(옵션, 30점): data/test_realtime.json → outputs/realtime_output.json.

흐름(질문 1건당):
  (1) 분류기로 label 예측           — src.chat_pipeline.classify 재사용
  (2) 라벨에 맞는 실시간 소스 라이브 크롤:
        · 식단(3)  → crawlers.dining.DiningCrawler   (mobileadmin.cnu.ac.kr/food)
        · 셔틀(4)  → crawlers.shuttle.ShuttleCrawler (plus.cnu.ac.kr 셔틀)
        · 공지(1)  → crawlers.notices.NoticesCrawler (학교/학과 공지 최신글)
        · 그외(0,2)→ 정적 RAG 폴백 (src.chat_pipeline.chat_answer)
  (3) 가져온 최신 본문을 컨텍스트로 답변 생성:
        - generation.llm.generate (로컬 EXAONE/Qwen)
        - 모델을 못 올리면(REALTIME_STUB=1 또는 로드 실패) 크롤 본문 요약 스텁으로 포맷만.
  → outputs/realtime_output.json [{"user","model"}] 저장.

크롤 실패 시 graceful: "실시간 정보를 가져오지 못했습니다" 폴백.
정성평가 기준 = 실시간 변하는 정보(셔틀/식단/공지)를 라이브로 가져와 최신성·정확성 확보.

환경:
  REALTIME_STUB=1   생성모델 미로드, 크롤 본문 요약으로 model 칸 채움(포맷·라이브성 검증).
  REALTIME_MAX_DOCS 크롤 결과 중 컨텍스트로 쓸 최대 청크 수(기본 4).

실행: python src/realtime_model.py
"""
import os
import sys
import json
from pathlib import Path

try:
    ROOT = Path(__file__).resolve().parent.parent
except NameError:
    ROOT = Path.cwd()
    if not (ROOT / "interface").exists() and (ROOT.parent / "interface").exists():
        ROOT = ROOT.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

TEST_PATH = ROOT / "data" / "test_realtime.json"
OUT_DIR = ROOT / "outputs"
OUT_PATH = OUT_DIR / "realtime_output.json"

STUB = os.environ.get("REALTIME_STUB", "0") == "1"
MAX_DOCS = int(os.environ.get("REALTIME_MAX_DOCS", "4"))

# 크롤 실패 폴백 문구
_CRAWL_FAIL_MSG = "실시간 정보를 가져오지 못했습니다."

# PDF 예시 질문(test_realtime.json 없을 때 샘플 생성용)
_SAMPLE_QUESTIONS = [
    "새로 업데이트된 셔틀버스 정류장이 있을까요?",
    "5월 이후로 변동된 학사일정이 있을까요?",
    "다음주 학식 뭐 나와요?",
    "가장 최근에 올라온 공지사항은 언제 게시되었나요?",
]

# label → 실시간 크롤러 (식단/셔틀/공지만 라이브 소스 보유)
_LIVE_LABELS = {1: "공지", 3: "식단", 4: "셔틀"}


def ensure_test_file():
    """test_realtime.json 없으면 PDF 예시로 샘플 생성."""
    if TEST_PATH.exists():
        return
    TEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    rows = [{"user": q} for q in _SAMPLE_QUESTIONS]
    with open(TEST_PATH, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    print(f"[init] test_realtime.json 없어 PDF 예시로 샘플 생성: {TEST_PATH} (n={len(rows)})")


def _safe_label(question: str) -> int:
    """분류기로 label 예측. 실패 시 -1(미분류)."""
    try:
        from src.chat_pipeline import classify
        return classify(question)
    except Exception as e:
        print(f"[realtime] 분류 실패({e}) → 미분류(-1)")
        return -1


def _live_crawl(label: int) -> list[dict]:
    """label 에 해당하는 실시간 소스를 라이브 크롤. 실패/해당없음 시 빈 리스트.

    crawlers/*.py 의 기존 크롤러를 재사용한다. safe_crawl() 은 사이트 접속 실패 시
    크롤러 내부 정적 폴백(_fallback/_static_fallback)으로 떨어지므로,
    여기서는 crawl() 을 직접 호출해 '라이브 성공'과 '폴백'을 구분한다.
    """
    try:
        if label == 3:
            from crawlers.dining import DiningCrawler
            crawler = DiningCrawler()
        elif label == 4:
            from crawlers.shuttle import ShuttleCrawler
            crawler = ShuttleCrawler()
        elif label == 1:
            from crawlers.notices import NoticesCrawler
            crawler = NoticesCrawler()
        else:
            return []
    except Exception as e:
        print(f"[realtime] 크롤러 임포트 실패(label={label}): {e}")
        return []

    try:
        docs = crawler.crawl()  # 라이브 시도(네트워크). 실패하면 예외 또는 내부 폴백.
    except Exception as e:
        print(f"[realtime] 라이브 크롤 실패(label={label}): {e} → safe_crawl 폴백 시도")
        try:
            docs = crawler.safe_crawl()
        except Exception as e2:
            print(f"[realtime] safe_crawl 도 실패(label={label}): {e2}")
            return []
    # crawl()이 사이트 실패 시 내부적으로 하드코딩 더미(_fallback)를 삼켜 반환할 수 있음.
    # is_fallback 마킹된 더미는 '라이브 성공'으로 오인되면 안 되므로 제거한다.
    # (식단 푸드코트·셔틀 정적표 등 실데이터 폴백은 마킹 없으므로 그대로 유지)
    live = [d for d in (docs or []) if not d.get("is_fallback")]
    if not live:
        print(f"[realtime] label={label}: 라이브 0건(더미만) → 상위 폴백")
    return live


def _docs_to_chunks(docs: list[dict]) -> list[dict]:
    """크롤 dict → build_user_prompt 가 기대하는 청크 포맷으로 변환(상위 MAX_DOCS)."""
    chunks = []
    for d in docs[:MAX_DOCS]:
        chunks.append({
            "text": d.get("content") or d.get("original_text") or d.get("title", ""),
            "source_url": d.get("source_url", ""),
            "last_crawled_at": d.get("last_crawled_at", ""),
            "valid_until": d.get("valid_until", ""),
            "freshness_tier": d.get("freshness_tier", ""),
        })
    return chunks


def _generate_from_live(question: str, chunks: list[dict]) -> str:
    """라이브 크롤 청크를 컨텍스트로 답변 생성(로컬 LLM). 실패 시 스텁 요약."""
    from generation.prompt import build_user_prompt, SYSTEM_PROMPT

    user_prompt = build_user_prompt(question, chunks)
    full_prompt = SYSTEM_PROMPT + "\n\n" + user_prompt

    if STUB:
        return _stub_from_chunks(question, chunks)

    try:
        from generation.llm import generate
        from interface.answer_questions import _clean_answer
        answer = generate(full_prompt, system_prompt=SYSTEM_PROMPT)
        answer = _clean_answer(answer)
    except Exception as e:
        print(f"[realtime] 생성 실패({e}) → 스텁 요약 폴백")
        return _stub_from_chunks(question, chunks)

    # 깨끗한 출처 1줄 부착(라이브 소스 URL)
    urls = []
    for c in chunks:
        u = c.get("source_url", "")
        if u and u not in urls:
            urls.append(u)
    if urls:
        answer = answer.rstrip() + "\n\n출처: " + ", ".join(urls[:3])
    return answer or _stub_from_chunks(question, chunks)


def _stub_from_chunks(question: str, chunks: list[dict]) -> str:
    """생성모델 없이 라이브 크롤 본문을 요약해 model 칸 채움(포맷·라이브성 검증)."""
    if not chunks:
        return _CRAWL_FAIL_MSG
    parts = []
    for c in chunks[:2]:
        text = (c.get("text") or "").strip().replace("\n", " ")
        if text:
            parts.append(text[:200])
    body = " / ".join(parts) if parts else _CRAWL_FAIL_MSG
    urls = [c.get("source_url", "") for c in chunks if c.get("source_url")]
    out = f"[실시간] {body}"
    if urls:
        out += f"\n출처: {urls[0]}"
    return out


def answer_realtime(question: str) -> str:
    """질문 1건 → 실시간 답변 문자열."""
    label = _safe_label(question)

    if label in _LIVE_LABELS:
        kind = _LIVE_LABELS[label]
        print(f"[realtime] label={label}({kind}) → 라이브 크롤")
        docs = _live_crawl(label)
        if not docs:
            return _CRAWL_FAIL_MSG
        chunks = _docs_to_chunks(docs)
        if not chunks:
            return _CRAWL_FAIL_MSG
        return _generate_from_live(question, chunks)

    # 그 외(졸업요건0/학사일정2/미분류) → 정적 RAG 폴백
    print(f"[realtime] label={label} → 정적 RAG 폴백(chat_answer)")
    if STUB:
        # 생성모델 미로드 모드: 정적 RAG(EXAONE) 대신 라이브 소스 없음을 명시.
        return f"[정적RAG-스텁] label={label}: 실시간 라이브 소스가 없는 질문(졸업요건/학사일정 등) → 정적 RAG 경로(생성 스텁)."
    try:
        from src.chat_pipeline import chat_answer
        return chat_answer(question)
    except Exception as e:
        print(f"[realtime] 정적 RAG 폴백 실패({e})")
        return _CRAWL_FAIL_MSG


def main():
    ensure_test_file()

    with open(TEST_PATH, encoding="utf-8") as f:
        rows = json.load(f)
    users = [r.get("user", r.get("question", "")) for r in rows]
    print(f"[env] REALTIME_STUB={STUB}  MAX_DOCS={MAX_DOCS}  n={len(users)}  in={TEST_PATH}")

    out = []
    for i, q in enumerate(users):
        print(f"[realtime] {i + 1}/{len(users)}: {q[:50]}")
        try:
            model_ans = answer_realtime(q)
        except Exception as e:
            model_ans = f"{_CRAWL_FAIL_MSG} (오류: {e})"
        out.append({"user": q, "model": model_ans})

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"[done] {len(out)}건 → {OUT_PATH}")
    for row in out[:4]:
        print("   ", json.dumps(row, ensure_ascii=False)[:200])


if __name__ == "__main__":
    main()
