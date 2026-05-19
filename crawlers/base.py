from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any


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
        """크롤 실패 시 반환할 더미 데이터 (5개)."""
        now = datetime.utcnow().isoformat()
        base_url = f"https://www.cnu.ac.kr/{self.category_id}/fallback"
        return [
            self._make_doc(
                title=f"{self.category_name} 샘플 {i+1}",
                content=f"[더미] {self.category_name} 카테고리 샘플 데이터 {i+1}번. 실제 크롤링 결과로 교체 예정.",
                source_url=base_url,
                now=now,
                valid=now,
            )
            for i in range(5)
        ]

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
