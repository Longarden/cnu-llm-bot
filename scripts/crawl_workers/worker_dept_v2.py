"""학과 풀데이터 워커: 자연8단과대 + 인문/사회/사범."""
import sys, json
from pathlib import Path
from datetime import datetime, timedelta

ROOT = Path('C:/Users/dmsak/cnu-llm-bot')
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

from crawlers.departments_natural_eng_pharm_med import crawl_all as crawl_natural
from crawlers.departments_humanities_social import crawl_all as crawl_hs

OUT = ROOT / 'data/crawled_staging/dept_full_v2.json'
DONE = ROOT / 'data/crawled_staging/dept_full_v2.done'


def main():
    now = datetime.utcnow().isoformat()
    valid = (datetime.utcnow() + timedelta(days=14)).isoformat()
    today = now[:10]

    print('=== [1/2] 자연/공/약/의/간호/수의/생활/농생 ===', flush=True)
    nat_docs, _ = crawl_natural(now, valid, today)
    print(f'  소계 {len(nat_docs)}', flush=True)

    print('=== [2/2] 인문/사회/경상/사범 ===', flush=True)
    hs_docs, _ = crawl_hs(now, valid, today)
    print(f'  소계 {len(hs_docs)}', flush=True)

    all_docs = nat_docs + hs_docs
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(all_docs, f, ensure_ascii=False, indent=2)
    DONE.write_text(str(len(all_docs)), encoding='utf-8')
    print(f'\n완료: {len(all_docs)}건 → {OUT}', flush=True)


if __name__ == '__main__':
    main()
