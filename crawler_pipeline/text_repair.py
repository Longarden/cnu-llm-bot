"""인코딩 깨짐(모지바케) 자동 복구.

원인: 한국어 페이지(EUC-KR/cp949)를 latin1/cp1252로 잘못 디코딩하면
'충남대' -> 'Ãæ³²´ë' 처럼 깨진다. 이를 라운드트립으로 되돌린다.

안전장치: 한글이 늘어나는 경우에만 교체한다. 멀쩡한 영어/한글은 절대 안 건드림.
정확도 최우선 정책에 따라 빌드/크롤 경로에 자동 적용.
"""
from typing import Any


def _hangul_count(s: str) -> int:
    return sum(1 for c in s if "가" <= c <= "힣")


def repair_encoding(s: str) -> str:
    """모지바케면 복구, 아니면 원본 반환. 한글 수가 늘어야만 교체(오작동 방지)."""
    if not s:
        return s
    base_h = _hangul_count(s)
    # 한글이 이미 있으면 정상/혼합 텍스트로 보고 손대지 않음
    if base_h > 0:
        return s
    best, best_h = s, base_h
    for back in ("latin1", "cp1252"):
        for dec in ("cp949", "euc-kr"):
            try:
                cand = s.encode(back).decode(dec)
            except (UnicodeError, LookupError):
                continue
            h = _hangul_count(cand)
            if h > best_h:
                best, best_h = cand, h
    return best


def clean_docs(docs: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """문서 리스트의 텍스트 필드를 복구. (복구된 docs, 변경된 문서 수) 반환."""
    fixed = 0
    for d in docs:
        changed = False
        for key in ("original_text", "title", "content"):
            v = d.get(key)
            if isinstance(v, str):
                r = repair_encoding(v)
                if r != v:
                    d[key] = r
                    changed = True
        if changed:
            fixed += 1
    return docs, fixed
