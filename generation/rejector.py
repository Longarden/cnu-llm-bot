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

# 도메인 밖 키워드 패턴 (간단 휴리스틱)
_OUT_OF_DOMAIN_KEYWORDS = [
    "서울대", "연세대", "고려대", "카이스트", "포스텍",
    "수능", "공무원 시험", "군대", "병역",
    "주식", "암호화폐", "코인",
    "날씨", "주가", "환율",
]


class RejectionResult:
    def __init__(self, rejected: bool, reason: str, message: str):
        self.rejected = rejected
        self.reason = reason   # "no_results" | "low_score" | "stale" | "out_of_domain"
        self.message = message


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

    # 3. 점수 기반 거절
    if top_score is None:
        # chunks에서 최고 점수 추출 (rrf_score > dense_score > score 순서)
        scores = []
        for chunk in retrieved_chunks:
            for key in ("rrf_score", "dense_score", "score"):
                val = chunk.get(key)
                if val is not None:
                    scores.append(float(val))
                    break
        top_score = max(scores) if scores else 0.0

    if top_score < SCORE_THRESHOLD:
        logger.info(f"거절: 점수 {top_score:.3f} < 임계값 {SCORE_THRESHOLD}")
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
