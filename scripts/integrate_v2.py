"""v2 통합: 모든 staging *_v2.json + sweep_*.json → all_dedup.json.

title-hash + source_url 기반 빠른 dedup. chroma 재빌드는 GPU 환경에서 별도 수행.
"""
import sys, json, shutil, re
from pathlib import Path
from datetime import date

ROOT = Path('C:/Users/dmsak/cnu-llm-bot')
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

ALL = ROOT / 'data/crawled/all_dedup.json'
STAGING = ROOT / 'data/crawled_staging'


def norm_title(t: str) -> str:
    return re.sub(r'\s+', ' ', (t or '').strip().lower())


def dedup_keyed(docs: list[dict]) -> list[dict]:
    best: dict[tuple, dict] = {}
    for d in docs:
        t = norm_title(d.get('title', ''))
        u = (d.get('source_url') or '').strip()
        if not t:
            continue
        k = (t, u)
        prev = best.get(k)
        if prev is None or len(d.get('original_text', '')) > len(prev.get('original_text', '')):
            best[k] = d
    return list(best.values())


def main():
    files = sorted(STAGING.glob('*_v2.json')) + sorted(STAGING.glob('sweep_*.json'))
    print(f'=== staging 파일 {len(files)}개 발견 ===')
    base = json.load(open(ALL, encoding='utf-8')) if ALL.exists() else []
    print(f'  base(all_dedup) {len(base)}건')
    combined = list(base)
    for f in files:
        try:
            d = json.load(open(f, encoding='utf-8'))
        except Exception as e:
            print(f'  [WARN] {f.name} 읽기 실패: {e}')
            continue
        combined.extend(d)
        print(f'  + {len(d):>5}건 {f.name}')
    print(f'\n  → 합계 {len(combined)}건')

    print('\n=== 인코딩 복구 + dedup ===')
    from crawler_pipeline.text_repair import clean_docs
    combined, fixed = clean_docs(combined)
    if fixed:
        print(f'  인코딩 복구 {fixed}건')
    deduped = dedup_keyed(combined)
    print(f'  dedup: {len(combined)} → {len(deduped)}')

    print('\n=== 백업 + all_dedup.json 갱신 ===')
    bak = ALL.with_name(f'all_dedup.json.v2_bak_{date.today().isoformat()}')
    if ALL.exists() and not bak.exists():
        shutil.copy(ALL, bak)
    with open(ALL, 'w', encoding='utf-8') as f:
        json.dump(deduped, f, ensure_ascii=False, indent=2)
    print(f'  저장: {len(deduped)}건 → {ALL.name} (백업 {bak.name})')

    print('\n=== 카테고리 분포 ===')
    from collections import Counter
    c = Counter(x.get('data_category', '?') for x in deduped)
    for k, v in sorted(c.items(), key=lambda x: -x[1]):
        print(f'  {k:<22} {v:>4}')
    print(f'\n=== 완료. 통합 후 총 {len(deduped)}건 ===')


if __name__ == '__main__':
    main()
