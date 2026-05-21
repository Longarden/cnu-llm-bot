"""Site exploration script - temporary, for development."""
import requests
from bs4 import BeautifulSoup
import json

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120'}


def fetch(url, timeout=15):
    r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
    # Try to detect encoding from content
    if 'euc-kr' in r.headers.get('Content-Type', '').lower():
        r.encoding = 'euc-kr'
    else:
        # Use apparent encoding from content
        from bs4 import BeautifulSoup as BS
        soup_raw = BS(r.content, 'html.parser')
        meta_charset = soup_raw.find('meta', charset=True)
        if meta_charset:
            r.encoding = meta_charset.get('charset', 'utf-8')
        else:
            meta_ct = soup_raw.find('meta', {'http-equiv': lambda x: x and x.lower() == 'content-type'})
            if meta_ct and 'charset' in meta_ct.get('content', '').lower():
                charset = meta_ct['content'].split('charset=')[-1].strip()
                r.encoding = charset
    return r


def get_links(soup, base_url):
    links = []
    for a in soup.find_all('a', href=True):
        href = a.get('href', '')
        text = a.get_text(strip=True)
        if text and len(text) > 1 and not href.startswith('#') and not href.startswith('javascript'):
            if href.startswith('/'):
                domain = '/'.join(base_url.split('/')[:3])
                href = domain + href
            links.append({'text': text, 'href': href})
    return links


def explore(name, url):
    print(f"\n=== {name} ===")
    try:
        r = fetch(url)
        soup = BeautifulSoup(r.content, 'html.parser', from_encoding=r.encoding)
        title = soup.title.get_text(strip=True) if soup.title else 'N/A'
        print(f"Title: {title}")
        print(f"Status: {r.status_code}, Encoding: {r.encoding}")
        links = get_links(soup, url)
        print(f"Links ({len(links)}):")
        for l in links[:25]:
            print(f"  {l['text'][:30]}: {l['href']}")
        # Get main text content
        main = soup.find('div', class_=lambda x: x and any(k in x for k in ['content', 'main', 'article', 'board']))
        if main:
            text = main.get_text(separator='\n', strip=True)
            print(f"Main content preview: {text[:300]}")
    except Exception as e:
        print(f"ERROR: {e}")


if __name__ == '__main__':
    sites = [
        ('computer.cnu.ac.kr 교수진', 'https://computer.cnu.ac.kr/computer/intro/faculty01.do'),
        ('computer.cnu.ac.kr 교육과정', 'https://computer.cnu.ac.kr/computer/edu/curriculum.do'),
        ('computer.cnu.ac.kr 학부소개', 'https://computer.cnu.ac.kr/computer/intro/greeting.do'),
        ('ee.cnu.ac.kr 메인', 'https://ee.cnu.ac.kr'),
        ('me.cnu.ac.kr 메인', 'https://me.cnu.ac.kr'),
        ('cnu.ac.kr/admin', 'https://plus.cnu.ac.kr'),
        ('cnu.ac.kr/intro', 'https://plus.cnu.ac.kr/html/kr/sub01/sub01_010101.html'),
    ]
    for name, url in sites:
        explore(name, url)
