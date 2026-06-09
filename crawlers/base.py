import os
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any


def fetch_with_retry(url: str, headers: dict | None = None,
                     timeout: int | None = None, retries: int | None = None):
    """GET + 재시도. 모두 실패하면 마지막 예외를 던진다.

    라이브 시연/채점에서 느린(또는 죽은) 학과 서버 한 곳이 라이브 크롤 전체를 100초
    터널 한도까지 끌어 524를 내는 것을 막기 위해, 기본 타임아웃을 짧게(8초) + 재시도 0회로
    둔다. 느린 서버는 빨리 포기하고 상위에서 정적 폴백 → 524 대신 즉시 답.
    환경변수 CRAWL_TIMEOUT / CRAWL_RETRIES 로 조정(호출부가 명시 인자를 주면 그 값 우선).
    """
    import requests
    if timeout is None:
        # (connect, read) 분리(requests 모범사례): 죽은/접속불가 호스트는 connect 단계에서 빨리 포기,
        # 살아있지만 느린 서버(plus.cnu 등)는 read 까지 기다린다. 단일값보다 헛대기를 줄임.
        connect_t = float(os.environ.get("CRAWL_CONNECT_TIMEOUT", "4"))
        read_t = float(os.environ.get("CRAWL_TIMEOUT", "15"))
        timeout = (connect_t, read_t)
    if retries is None:
        retries = int(os.environ.get("CRAWL_RETRIES", "0"))
    last = None
    for attempt in range(retries + 1):
        try:
            r = requests.get(url, timeout=timeout, headers=headers or {})
            r.raise_for_status()
            return r
        except Exception as e:
            last = e
    raise last


class BaseCrawler(ABC):
    """모든 카테고리 크롤러의 추상 기본 클래스.

    반환 dict 필수 키:
      source_url, data_category, last_crawled_at, valid_until,
      freshness_tier, original_text, title, content, date
    """

    category_id: str = ""
    category_name: str = ""
    freshness_tier: str = "semi_static"

    @abstractmethod
    def crawl(self) -> list[dict[str, Any]]:
        """실제 크롤링 수행. 실패 시 _fallback() 반환."""
        ...

    def _make_doc(self, title: str, content: str, source_url: str, now: str, valid: str, date: str = "") -> dict:
        """필수 키 6종 + title/content/date 를 포함한 문서 dict 생성 헬퍼."""
        # 인코딩 깨짐(모지바케) 자동 복구. 정상 텍스트는 그대로 통과.
        from crawler_pipeline.text_repair import repair_encoding
        title = repair_encoding(title)
        content = repair_encoding(content)
        return {
            "source_url": source_url,
            "data_category": self.category_id,
            "last_crawled_at": now,
            "valid_until": valid,
            "freshness_tier": self.freshness_tier,
            "original_text": content,
            "title": title,
            "content": content,
            "date": date or now[:10],
        }

    def _fallback(self) -> list[dict[str, Any]]:
        """크롤 실패 시 반환할 더미 데이터 (5개).

        is_fallback=True 로 마킹한다 → 실시간 경로(realtime_model._live_crawl)가
        이 더미를 '라이브 성공'으로 오인해 사용자에게 내보내지 않고 걸러낸다.
        """
        now = datetime.utcnow().isoformat()
        base_url = f"https://www.cnu.ac.kr/{self.category_id}/fallback"
        docs = [
            self._make_doc(
                title=f"{self.category_name} 샘플 {i+1}",
                content=f"[더미] {self.category_name} 카테고리 샘플 데이터 {i+1}번. 실제 크롤링 결과로 교체 예정.",
                source_url=base_url,
                now=now,
                valid=now,
            )
            for i in range(5)
        ]
        for d in docs:
            d["is_fallback"] = True
        return docs

    def safe_crawl(self) -> list[dict[str, Any]]:
        """크롤링 시도 후 실패하면 _fallback() 반환."""
        try:
            result = self.crawl()
            if not result:
                return self._fallback()
            return result
        except Exception as e:
            print(f"[{self.category_id}] 크롤 실패: {e} → fallback 사용")
            return self._fallback()
