"""거절 판정 + 카테고리 라우팅 순수 로직 단위테스트 (GPU 불필요).

생성/임베딩 없이 돌아가는 부분만 검증한다:
  - generation.rejector.check_rejection 의 밴드/엣지케이스
  - interface.answer_questions._soft_route_by_category
  - src.chat_pipeline.LABEL_TO_CATEGORY 매핑 정합성

실행: python -m pytest tests/test_rejection_routing.py -q
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from generation.rejector import check_rejection
from interface.answer_questions import _soft_route_by_category


# ── check_rejection ────────────────────────────────────────────────
def test_out_of_domain_rejected():
    r = check_rejection("서울대 입학 요건 알려줘", [{"dense_score": 0.9}])
    assert r.rejected and r.reason == "out_of_domain"


def test_empty_chunks_rejected():
    r = check_rejection("졸업요건 뭐야", [])
    assert r.rejected and r.reason == "no_results"


def test_high_dense_score_passes():
    chunks = [{"dense_score": 0.62, "sparse_score": 0.0, "valid_until": ""}]
    r = check_rejection("졸업 학점 몇 학점이야", chunks)
    assert not r.rejected


def test_low_dense_score_rejected():
    chunks = [{"dense_score": 0.12, "sparse_score": 0.0, "valid_until": ""}]
    r = check_rejection("아주 동떨어진 질문", chunks)
    assert r.rejected and r.reason == "low_score"


def test_chunks_without_score_info_pass():
    """점수 키가 전혀 없는 청크 + 비어있지 않음 → 오거절하지 않고 통과(엣지케이스 픽스)."""
    chunks = [{"original_text": "충남대 학사 안내", "valid_until": ""}]
    r = check_rejection("학사 안내", chunks)
    assert not r.rejected, "점수 정보 없으면 0점 강제거절 대신 통과해야 함"


def test_rerank_band_correct_passes():
    chunks = [{"rerank_score": 0.80, "valid_until": ""}]
    r = check_rejection("질문", chunks)
    assert not r.rejected and r.grade == "correct"


def test_rerank_band_ambiguous_passes_with_caveat():
    chunks = [{"rerank_score": 0.57, "valid_until": ""}]
    r = check_rejection("질문", chunks)
    assert not r.rejected and r.grade == "ambiguous" and r.caveat


def test_rerank_band_incorrect_rejected():
    chunks = [{"rerank_score": 0.20, "valid_until": ""}]
    r = check_rejection("질문", chunks)
    assert r.rejected and r.grade == "incorrect"


# ── _soft_route_by_category ────────────────────────────────────────
def _doc(cat, text="t"):
    return {"data_category": cat, "original_text": text, "metadata": {"data_category": cat}}


def test_soft_route_list_hint_reorders_matched_first():
    docs = [_doc("F_department"), _doc("A_shuttle"), _doc("A_shuttle")]
    out = _soft_route_by_category(docs, ["A_shuttle"])
    assert out[0]["data_category"] == "A_shuttle"
    assert out[-1]["data_category"] == "F_department"  # 비매칭은 뒤로 폴백 유지


def test_soft_route_string_hint_backcompat():
    docs = [_doc("K_notices"), _doc("B_academic"), _doc("K_notices")]
    out = _soft_route_by_category(docs, "K_notices")
    assert out[0]["data_category"] == "K_notices"


def test_soft_route_sparse_match_falls_back_to_all():
    # 매칭이 min_keep(2) 미만이면 전체 그대로 폴백
    docs = [_doc("F_department"), _doc("B_academic"), _doc("A_dining")]
    out = _soft_route_by_category(docs, ["A_dining"])
    assert out == docs


def test_soft_route_no_hint_passthrough():
    docs = [_doc("F_department")]
    assert _soft_route_by_category(docs, None) == docs


# ── stale 소프트 처리(거절 대신 기준일 단서) ──────────────────────
def test_stale_not_rejected_gives_caveat():
    chunks = [{"dense_score": 0.6, "sparse_score": 0.0, "valid_until": "2020-01-01"}]
    r = check_rejection("비교과 프로그램 공지 있어?", chunks)
    assert not r.rejected, "만료돼도 거절 말고 정보+기준일로 답해야 함"
    assert r.caveat and "2020-01-01" in r.caveat


# ── 출처 마크다운 중복 컷(_clean_answer) ──────────────────────────
def test_clean_answer_cuts_markdown_source():
    from interface.answer_questions import _clean_answer
    a = "졸업 학점은 130학점입니다.\n\n**출처**: [링크](http://x)"
    out = _clean_answer(a)
    assert "130학점" in out
    assert "출처" not in out  # 모델이 쓴 출처 꼬리는 제거(우리가 깨끗한 1줄 재부착)


# ── 학부 우선 필터(_deprioritize_grad) ────────────────────────────
def test_deprioritize_grad_moves_grad_to_back():
    from interface.answer_questions import _deprioritize_grad
    docs = [
        {"source_url": "https://medicine.cnu.ac.kr/medicine/grad/change-grad.do", "title": "대학원 전과", "original_text": "g"},
        {"source_url": "https://plus.cnu.ac.kr/html/affairs.html", "title": "학부 전과", "original_text": "u"},
    ]
    out = _deprioritize_grad(docs)
    assert out[0]["title"] == "학부 전과"   # 학부가 앞으로
    assert out[-1]["title"] == "대학원 전과"  # 대학원은 뒤로(드롭 아님)


def test_deprioritize_grad_all_grad_keeps_original():
    from interface.answer_questions import _deprioritize_grad
    docs = [{"source_url": "x/grad", "title": "대학원만"}]
    assert _deprioritize_grad(docs) == docs  # 전부 대학원이면 원본 유지


# ── 식단 홀-인지 청크 선택(_docs_to_chunks) ────────────────────────
def test_docs_to_chunks_hall_aware_includes_queried_hall():
    """제2학생회관이 5번째여도 질문에 맞춰 상위로 끌려와 컨텍스트에 포함돼야 함."""
    from src.realtime_model import _docs_to_chunks
    docs = [
        {"title": "충남대 학식 [d] 구분 조식", "content": "구분 조식"},
        {"title": "충남대 학식 [d] 제1학생회관 조식", "content": "제1학생회관 조식 메뉴"},
        {"title": "충남대 학식 [d] 구분 중식", "content": "구분 중식"},
        {"title": "충남대 학식 [d] 제1학생회관 중식", "content": "제1학생회관 중식 메뉴"},
        {"title": "충남대 학식 [d] 제2학생회관 중식", "content": "제2학생회관 중식 메뉴 김치찌개"},
    ]
    chunks = _docs_to_chunks(docs, "제2학생회관 오늘 점심 뭐 나와?")
    joined = " ".join(c["text"] for c in chunks)
    assert "제2학생회관" in joined, "질문한 학생회관이 컨텍스트에 포함돼야 함"


# ── 중국어 누출 제거(_strip_foreign_lines) ────────────────────────
def test_strip_foreign_lines_removes_chinese_keeps_korean():
    from interface.answer_questions import _strip_foreign_lines
    leaked = (
        "계절학기 수강신청 일정은 다음과 같습니다:\n"
        "- 하기 계절학기: 5월 중\n"
        "- 동기 계절학기: 11월 중\n"
        "具体的的地说，就是：\n"
        "- 下学期：5月中旬\n"
        "- 春季学期：11月中旬\n"
        "这些日期可能会有所变动，请以学校官方通知为准。"
    )
    out = _strip_foreign_lines(leaked)
    assert "계절학기" in out and "5월 중" in out      # 한국어 유지
    assert "下学期" not in out and "具体" not in out   # 중국어 제거


def test_strip_foreign_lines_keeps_korean_with_hanja():
    from interface.answer_questions import _strip_foreign_lines
    s = "졸업 學점은 140學점 이상입니다."  # 한글+한자 혼용 한국어 → 유지
    assert _strip_foreign_lines(s) == s


def test_strip_foreign_lines_all_foreign_keeps_original():
    from interface.answer_questions import _strip_foreign_lines
    s = "完成所有必修课程\n达到学分要求"  # 전부 중국어면 과삭제 방지로 원본 유지
    assert _strip_foreign_lines(s) == s


# ── LABEL_TO_CATEGORY 정합성 ───────────────────────────────────────
def test_label_category_mapping():
    from src.chat_pipeline import LABEL_TO_CATEGORY, LABEL_NAMES
    assert set(LABEL_TO_CATEGORY) == {0, 1, 2, 3, 4}
    assert LABEL_TO_CATEGORY[3] == ["A_dining"]
    assert LABEL_TO_CATEGORY[4] == ["A_shuttle"]
    assert set(LABEL_NAMES) == {0, 1, 2, 3, 4}
