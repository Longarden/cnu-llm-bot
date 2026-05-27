"""학과 sweep 등에서 들어온 빈약/메뉴-only 잔재 청소.

조건 (보수적 — 의미 있는 짧은 본문은 보존):
  len < 200 자 AND
  (
    노이즈 키워드 >=2개 (자바스크립트/바로가기/주메뉴/서브메뉴/사이트맵 등)
    OR "|" 토큰 ≥5개 + 평균토큰 길이<15자 (게시판 헤더만)
  )

먼저 dry-run으로 영향 확인 → 사용자가 확정하면 실 제거.
실행: python scripts/cleanup_thin_noise.py        (제거 후 저장)
      python scripts/cleanup_thin_noise.py --dry-run
"""
import sys, json, shutil, re
from pathlib import Path
from datetime import date
from collections import Counter

ROOT = Path('C:/Users/dmsak/cnu-llm-bot')
ALL = ROOT / 'data/crawled/all_dedup.json'
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

NOISE_TOKENS = [
    '자바스크립트', '바로가기', '주메뉴', '서브메뉴', '모바일 메뉴', '사이트맵',
    '로그인', '통합검색', 'CNU With U', '발전기금', '번역이 완료',
    '본문 바로가기', '검색 결과를', '전체메뉴',
]


def is_thin_noise(text: str) -> tuple[bool, str]:
    t = (text or '').strip()
    if len(t) >= 200:
        return False, ''
    if len(t) < 30:
        return True, 'too_short<30'
    noise = sum(1 for k in NOISE_TOKENS if k in t)
    if noise >= 2:
        return True, f'noise_hits={noise}'
    # 게시판 헤더("|" 구분 메뉴 행) 패턴
    tokens = [tk.strip() for tk in t.split('|') if tk.strip()]
    if len(tokens) >= 5:
        avg = sum(len(tk) for tk in tokens) / len(tokens)
        if avg < 15:
            return True, f'pipe_menu(tokens={len(tokens)} avg={avg:.1f})'
    # 한국어 종결문 패턴 검사: 가-힣 + 다/요/음/니 종결 OR 마침표 종결
    has_sentence = bool(
        re.search(r'[가-힣]{2,}[가-힣\s,()0-9A-Za-z%·,.-]{8,}[\.다요습음]', t)
    )
    if not has_sentence and noise >= 1:
        return True, f'no_sentence+noise={noise}'
    return False, ''


def main():
    dry = '--dry-run' in sys.argv
    docs = json.load(open(ALL, encoding='utf-8'))
    print(f'before {len(docs)}건')

    kept, removed = [], []
    reasons = Counter()
    for d in docs:
        noise, reason = is_thin_noise(d.get('original_text') or '')
        if noise:
            removed.append(d)
            reasons[reason] += 1
        else:
            kept.append(d)

    print(f'제거 대상: {len(removed)}건  ({len(removed)/len(docs)*100:.1f}%)')
    print('사유 분포:')
    for r, n in reasons.most_common():
        print(f'  {n:>4}  {r}')
    if removed:
        # 카테고리
        cat = Counter(x.get('data_category', '?') for x in removed)
        print('카테고리:')
        for k, v in cat.most_common():
            print(f'  {v:>4}  {k}')
        # 샘플 5
        print('샘플 5:')
        import random; random.seed(0)
        for x in random.sample(removed, min(5, len(removed))):
            t = (x.get('original_text', '') or '').replace('\n', '|')[:90]
            print(f'  [{len(x.get("original_text",""))}자] {x["source_url"][:70]}')
            print(f'      {t}')

    if dry:
        print('\n(dry-run: 파일 안 건드림)')
        return

    bak = ALL.with_name(f'all_dedup.json.thinnoise_bak_{date.today().isoformat()}')
    if ALL.exists() and not bak.exists():
        shutil.copy(ALL, bak)
    with open(ALL, 'w', encoding='utf-8') as f:
        json.dump(kept, f, ensure_ascii=False, indent=2)
    print(f'\n저장: {len(kept)}건  (백업 {bak.name})')
    print(f'before {len(docs)} → after {len(kept)}  (제거 {len(docs) - len(kept)})')


if __name__ == '__main__':
    main()
