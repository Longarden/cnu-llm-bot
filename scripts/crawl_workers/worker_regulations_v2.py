"""학사규정 워커: 학칙 8편 HWP 수집."""
import sys, json
from pathlib import Path

ROOT = Path('C:/Users/dmsak/cnu-llm-bot')
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

from scripts.collect_regulations_admission import collect_rules

OUT = ROOT / 'data/crawled_staging/regulations_v2.json'
DONE = ROOT / 'data/crawled_staging/regulations_v2.done'


def main():
    docs, report = collect_rules()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(docs, f, ensure_ascii=False, indent=2)
    DONE.write_text(str(len(docs)), encoding='utf-8')
    print(f'\n완료: {len(docs)}건 → {OUT}', flush=True)


if __name__ == '__main__':
    main()
