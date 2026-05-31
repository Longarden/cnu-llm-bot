"""빈약/메뉴잡음 문서 페이지에서 콘텐츠 이미지 수집 → 폴더 + 매핑.

본문이 이미지에 갇힌 페이지(pharm 교육목표 등)의 이미지를 모아둠.
사용자가 이 폴더를 외부 멀티모달 LLM에 넣어 텍스트화 → 나중에 해당 문서에 반영.

출력: data/content_images/ (이미지들) + _mapping.json (이미지↔출처문서)
실행: python scripts/collect_content_images.py
"""
import sys, os, json, re, hashlib
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

ALL = ROOT / 'data' / 'crawled' / 'all_dedup.json'
OUT = ROOT / 'data' / 'content_images'
OUT.mkdir(parents=True, exist_ok=True)
HDR = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

# 로고/아이콘/배너 등 비콘텐츠 이미지 제외 (img-ob 같은 콘텐츠는 살림)
EXCLUDE = ['logo', 'icon', 'btn', 'banner', 'common', 'sns', 'symbol',
           '_bg', 'footer', 'header', 'gnb', 'menu', 'sprite', 'blank', 'spacer']
MIN_BYTES = 6000   # 6KB 미만(아이콘류) 제외


def is_menu(body):
    lines = [l.strip() for l in (body or '').split('\n') if l.strip()]
    if len(lines) < 5:
        return False
    return sum(1 for l in lines if len(l) < 10) / len(lines) > 0.6


def main():
    d = json.load(open(ALL, encoding='utf-8'))
    targets = [x for x in d
               if len((x.get('original_text', '') or '').strip()) < 200
               or is_menu(x.get('original_text', ''))]
    print(f'대상 문서(빈약/메뉴잡음) {len(targets)}건 페이지 스캔', flush=True)

    mapping, seen, dl = [], set(), 0
    for i, x in enumerate(targets):
        u = x.get('source_url', '') or ''
        if not u.startswith('http'):
            continue
        try:
            r = requests.get(u, timeout=12, headers=HDR)
            soup = BeautifulSoup(r.text, 'html.parser')
        except Exception:
            continue
        for img in soup.find_all('img'):
            src = img.get('src', '') or img.get('data-src', '')
            if not src or not re.search(r'\.(jpg|jpeg|png|gif)', src, re.I):
                continue
            if any(k in src.lower() for k in EXCLUDE):
                continue
            full = urljoin(u, src)
            if full in seen:
                continue
            seen.add(full)
            try:
                ir = requests.get(full, timeout=12, headers=HDR)
                if len(ir.content) < MIN_BYTES:
                    continue
                ext = re.search(r'\.(jpg|jpeg|png|gif)', full, re.I).group(1).lower()
                fn = hashlib.md5(full.encode()).hexdigest()[:12] + '.' + ext
                with open(OUT / fn, 'wb') as f:
                    f.write(ir.content)
                mapping.append({
                    'image': fn,
                    'image_url': full,
                    'source_doc': u,
                    'category': x.get('data_category', ''),
                    'title': x.get('title', ''),
                })
                dl += 1
            except Exception:
                continue
        if (i + 1) % 30 == 0:
            print(f'  {i+1}/{len(targets)} 페이지, 이미지 {dl}개', flush=True)
            json.dump(mapping, open(OUT / '_mapping.json', 'w', encoding='utf-8'),
                      ensure_ascii=False, indent=2)

    json.dump(mapping, open(OUT / '_mapping.json', 'w', encoding='utf-8'),
              ensure_ascii=False, indent=2)
    print(f'\n완료: 이미지 {dl}개 → {OUT}', flush=True)
    print(f'매핑: {OUT / "_mapping.json"}', flush=True)
    print('→ 이 폴더를 멀티모달 LLM에 넣어 텍스트화 후 돌려주면 해당 문서에 반영', flush=True)


if __name__ == '__main__':
    main()
