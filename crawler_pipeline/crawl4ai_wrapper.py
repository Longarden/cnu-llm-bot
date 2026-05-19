"""Crawl4AI 비동기 래퍼. 병렬 20, T4 RAM 안전."""
import asyncio
import os
from typing import Optional


async def _fetch_one(url: str) -> Optional[str]:
    try:
        from crawl4ai import AsyncWebCrawler
        async with AsyncWebCrawler() as crawler:
            result = await crawler.arun(url=url)
            return result.markdown if result.success else None
    except Exception as e:
        print(f"[crawl4ai] {url} 실패: {e}")
        return None


async def fetch_urls_async(urls: list[str], concurrency: int = 20) -> list[dict]:
    """URL 목록을 병렬로 크롤링. 결과 dict 리스트 반환."""
    semaphore = asyncio.Semaphore(concurrency)

    async def bounded_fetch(url: str) -> dict:
        async with semaphore:
            content = await _fetch_one(url)
            return {"url": url, "content": content}

    tasks = [bounded_fetch(url) for url in urls]
    return await asyncio.gather(*tasks)


def fetch_urls(urls: list[str], concurrency: int = 20) -> list[dict]:
    """동기 진입점."""
    return asyncio.run(fetch_urls_async(urls, concurrency))
