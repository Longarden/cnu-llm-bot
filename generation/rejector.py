"""
거절 메커니즘 (AC8 준수).

거절 조건:
  1. 검색 최고 점수 < SCORE_THRESHOLD (기본 0.6)
  2. 최상위 청크의 freshness_tier 가 stale (valid_until 이 오늘 이전)
  3. 검색 결과 자체가 없음

거절 시: "제공된 자료에 해당 정보가 없습니다" 포함 메시지 반환.
"""

import os
import logging
from datetime import date
from typing import Optional

logger = logging.getLogger(__name__)

SCORE_THRESHOLD = float(os.environ.get("REJECT_THRESHOLD", "0.6"))
# 거절 판정용 임계값은 점수 종류별로 스케일이 다르다.
# - dense_score: 코사인 유사도(0~1). bge-m3 관련 청크는 보통 0.4 이상.
# - sparse_score: BM25(비유계, 0~수십). 용어 겹치면 수치가 큼.
# rrf_score(최대 ~0.033)는 순위융합 점수라 거절 판정에 쓰지 않는다.
DENSE_THRESHOLD = float(os.environ.get("REJECT_DENSE_THRESHOLD", "0.35"))
SPARSE_THRESHOLD = float(os.environ.get("REJECT_SPARSE_THRESHOLD", "3.0"))

# CRAG 3밴드 (크로스인코더 리랭커 점수 0~1 기준, 보정 데이터로 도출).
# Correct >= RERANK_CORRECT: 자료에 답 있음 -> 답변
# Ambiguous: 부분 매칭 -> 답변하되 단서(확인 필요) 추가 (배치 제출은 되묻기 불가)
# Incorrect < RERANK_INCORRECT: 매칭 없음 -> 거절
RERANK_CORRECT = float(os.environ.get("REJECT_RERANK_CORRECT", "0.62"))
RERANK_INCORRECT = float(os.environ.get("REJECT_RERANK_INCORRECT", "0.53"))

# 도메인 밖 키워드 패턴 (간단 휴리스틱)
_OUT_OF_DOMAIN_KEYWORDS = [
    "서울대", "연세대", "고려대", "카이스트", "포스텍",
    "수능", "공무원 시험", "군대", "병역",
    "주식", "암호화폐", "코인",
    "날씨", "주가", "환율",
]


class RejectionResult:
    def __init__(self, rejected: bool, reason: str, message: str,
                 grade: str = "correct", caveat: str = ""):
        self.rejected = rejected
        self.reason = reason   # "no_results" | "low_relevance" | "low_score" | "stale" | "out_of_domain" | "ambiguous"
        self.message = message
        self.grade = grade     # CRAG 등급: "correct" | "ambiguous" | "incorrect"
        self.caveat = caveat   # ambiguous일 때 답변에 덧붙일 단서(거절 아님)


def _is_stale(chunk: dict) -> bool:
    """valid_until 이 오늘 이전이면 stale."""
    valid_until = chunk.get("valid_until", "")
    if not valid_until:
        return False
    try:
        from datetime import datetime
        expiry = datetime.strptime(valid_until[:10], "%Y-%m-%d").date()
        return expiry < date.today()
    except (ValueError, TypeError):
        return False


def _stale_result(chunk: dict) -> "RejectionResult":
    """최상위 청크 만료(stale) 거절 결과."""
    logger.info("거절: 최상위 청크 만료(stale)")
    valid_until = chunk.get("valid_until", "알 수 없음")
    return RejectionResult(
        rejected=True, reason="stale", grade="incorrect",
        message=(
            f"해당 정보의 유효 기간({valid_until})이 지났습니다.\n"
            "최신 정보는 충남대학교 공식 홈페이지(www.cnu.ac.kr) 또는 "
            "해당 부서에 직접 문의해 주세요."
        ),
    )


def _is_out_of_domain(question: str) -> bool:
    """간단한 키워드 기반 도메인 밖 판별."""
    q_lower = question.lower()
    return any(kw in q_lower for kw in _OUT_OF_DOMAIN_KEYWORDS)


def check_rejection(
    question: str,
    retrieved_chunks: list[dict],
    top_score: Optional[float] = None,
) -> RejectionResult:
    """
    거절 여부 판정.

    Args:
        question: 사용자 질문
        retrieved_chunks: 검색된 청크 리스트 (rrf_score 또는 score 키 포함)
        top_score: 직접 최고 점수 전달 시 사용 (없으면 chunks에서 추출)

    Returns:
        RejectionResult
    """
    # 1. 도메인 밖 체크
    if _is_out_of_domain(question):
        return RejectionResult(
            rejected=True,
            reason="out_of_domain",
            message=(
                "충남대학교 학내 정보 범위를 벗어난 질문입니다.\n"
                "충남대학교 관련 학사, 시설, 장학, 취업 등에 관한 질문을 해 주세요."
            ),
        )

    # 2. 검색 결과 없음
    if not retrieved_chunks:
        return RejectionResult(
            rejected=True,
            reason="no_results",
            message=(
                "제공된 자료에 해당 정보가 없습니다.\n"
                "관련 학과 사무실이나 충남대학교 포털(portal.cnu.ac.kr)을 이용해 주세요."
            ),
        )

    # 3. CRAG 관련도 판정 (리랭커 점수 우선)
    # 크로스인코더 리랭커 점수(0~1)가 가장 정확한 절대 관련도 신호.
    # 있으면 3밴드로 판정하고, 없으면(리랭커 off/실패) dense/sparse 폴백.
    if top_score is None:
        rerank_scores = [float(c["rerank_score"]) for c in retrieved_chunks
                         if c.get("rerank_score") is not None]
        if rerank_scores:
            top_rr = max(rerank_scores)
            if top_rr < RERANK_INCORRECT:
                logger.info(f"거절(CRAG incorrect): rerank {top_rr:.3f} < {RERANK_INCORRECT}")
                return RejectionResult(
                    rejected=True, reason="low_relevance", grade="incorrect",
                    message=(
                        "제공된 자료에 해당 정보가 없습니다.\n"
                        "더 구체적인 질문으로 다시 시도하거나 충남대학교 포털"
                        "(plus.cnu.ac.kr)을 확인해 주세요."
                    ),
                )
            if top_rr < RERANK_CORRECT:
                # 부분 매칭: 거절하지 않고 단서를 달아 최선 답변(배치 제출은 되묻기 불가)
                if retrieved_chunks and _is_stale(retrieved_chunks[0]):
                    return _stale_result(retrieved_chunks[0])
                return RejectionResult(
                    rejected=False, reason="ambiguous", grade="ambiguous", message="",
                    caveat="제공된 자료가 질문과 부분적으로만 일치합니다. "
                           "정확한 내용은 충남대학교 포털에서 확인해 주세요.",
                )
            # correct -> stale 체크 후 통과
            if retrieved_chunks and _is_stale(retrieved_chunks[0]):
                return _stale_result(retrieved_chunks[0])
            return RejectionResult(rejected=False, reason="", message="", grade="correct")

    # 3-폴백. dense 코사인이 있으면 그것으로(0~1), 없으면 BM25 sparse로 판정.
    # rrf_score는 스케일이 너무 작아(최대 ~0.033) 절대 임계값에 부적합 -> 제외.
    if top_score is not None:
        threshold = SCORE_THRESHOLD
    else:
        dense_scores, sparse_scores, raw_scores = [], [], []
        for chunk in retrieved_chunks:
            for key, bucket in (("dense_score", dense_scores),
                                ("sparse_score", sparse_scores),
                                ("score", raw_scores)):
                val = chunk.get(key)
                if val is not None:
                    bucket.append(float(val))
        if any(v > 0 for v in dense_scores):
            top_score = max(dense_scores)
            threshold = DENSE_THRESHOLD
        elif any(v > 0 for v in sparse_scores):
            top_score = max(sparse_scores)
            threshold = SPARSE_THRESHOLD
        elif raw_scores:  # score만 있는 경우(코사인 가정)
            top_score = max(raw_scores)
            threshold = DENSE_THRESHOLD
        else:
            top_score = 0.0
            threshold = DENSE_THRESHOLD

    if top_score < threshold:
        logger.info(f"거절: 점수 {top_score:.3f} < 임계값 {threshold}")
        return RejectionResult(
            rejected=True,
            reason="low_score",
            message=(
                f"제공된 자료에 해당 정보가 없습니다. "
                f"(검색 유사도: {top_score:.2f})\n"
                "더 구체적인 질문으로 다시 시도하거나 학교 포털을 확인해 주세요."
            ),
        )

    # 4. Freshness 기반 거절 (최상위 청크 stale 여부)
    if retrieved_chunks and _is_stale(retrieved_chunks[0]):
        logger.info("거절: 최상위 청크 만료(stale)")
        valid_until = retrieved_chunks[0].get("valid_until", "알 수 없음")
        return RejectionResult(
            rejected=True,
            reason="stale",
            message=(
                f"해당 정보의 유효 기간({valid_until})이 지났습니다.\n"
                "최신 정보는 충남대학교 공식 홈페이지(www.cnu.ac.kr) 또는 "
                "해당 부서에 직접 문의해 주세요."
            ),
        )

    return RejectionResult(rejected=False, reason="", message="")
