"""Site exploration - outputs to JSON file."""
import requests
from bs4 import BeautifulSoup
import json

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120'}


def fetch_soup(url, timeout=15):
    r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
    soup = BeautifulSoup(r.content, 'html.parser')
    meta = soup.find('meta', attrs={'http-equiv': lambda x: x and x.lower() == 'content-type'})
    enc = 'utf-8'
    if meta and 'charset=' in meta.get('content', ''):
        enc = meta['content'].split('charset=')[-1].strip().lower()
    soup = BeautifulSoup(r.content, 'html.parser', from_encoding=enc)
    return soup, r.status_code, enc


def explore(url):
    soup, status, enc = fetch_soup(url)
    title = soup.title.get_text(strip=True) if soup.title else ''
    links = []
    for a in soup.find_all('a', href=True):
        href = a.get('href', '')
        text = a.get_text(strip=True)
        if text and len(text) > 1 and href and not href.startswith('#') and 'javascript' not in href:
            if href.startswith('/'):
                domain = '/'.join(url.split('/')[:3])
                href = domain + href
            links.append({'text': text[:40], 'href': href})
    # Get body text sample
    body = soup.get_text(separator=' ', strip=True)
    return {
        'url': url,
        'status': status,
        'encoding': enc,
        'title': title,
        'links': links[:30],
        'body_sample': body[:500]
    }


sites = [
    'https://computer.cnu.ac.kr/computer/intro/faculty01.do',
    'https://computer.cnu.ac.kr/computer/edu/curriculum.do',
    'https://computer.cnu.ac.kr/computer/intro/greeting.do',
    'https://ee.cnu.ac.kr',
    'https://me.cnu.ac.kr',
    'https://plus.cnu.ac.kr/html/kr/sub01/sub01_010101.html',
    'https://plus.cnu.ac.kr/html/kr/sub01/sub01_010201.html',
    'https://plus.cnu.ac.kr/html/kr/sub06/sub06_010101.html',
]

results = {}
for url in sites:
    try:
        results[url] = explore(url)
    except Exception as e:
        results[url] = {'error': str(e)}

with open('crawlers/explore_output.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print("Done. Results in crawlers/explore_output.json")
