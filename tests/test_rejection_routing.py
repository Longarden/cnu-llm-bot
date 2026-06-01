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


# ── LABEL_TO_CATEGORY 정합성 ───────────────────────────────────────
def test_label_category_mapping():
    from src.chat_pipeline import LABEL_TO_CATEGORY, LABEL_NAMES
    assert set(LABEL_TO_CATEGORY) == {0, 1, 2, 3, 4}
    assert LABEL_TO_CATEGORY[3] == ["A_dining"]
    assert LABEL_TO_CATEGORY[4] == ["A_shuttle"]
    assert set(LABEL_NAMES) == {0, 1, 2, 3, 4}
