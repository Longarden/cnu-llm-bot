import requests
from bs4 import BeautifulSoup
from typing import Optional


def discover_urls(base_url: str, max_urls: int = 200) -> list[str]:
    """sitemap.xml 파싱 후 URL 목록 반환. 실패 시 빈 리스트."""
    urls: list[str] = []
    sitemap_url = base_url.rstrip("/") + "/sitemap.xml"
    try:
        resp = requests.get(sitemap_url, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "xml")
        for loc in soup.find_all("loc")[:max_urls]:
            urls.append(loc.text.strip())
    except Exception as e:
        print(f"[sitemap_discoverer] {sitemap_url} 실패: {e}")
    return urls
