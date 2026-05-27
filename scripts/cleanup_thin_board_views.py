"""plus 게시판 view 중 본문 빈약(< 200자)인 행을 all_dedup.json에서 제거.

조건:
  - source_url 에 '_prog/_board/' 또는 '/bbs/' 패턴 (게시판 view)
  - AND len(original_text) < 200
근거: trafilatura가 plus 게시판 view 페이지에서 본문(첨부/요약) 못 가져옴.
      메타데이터(작성자/등록일/조회수)만 들어있어 RAG에 도움 안 됨.
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
MIN_LEN = 200
BOARD_PAT = re.compile(r'(/_prog/_board/|/bbs/)')


def is_thin_board(x: dict) -> bool:
    url = x.get('source_url') or ''
    if not BOARD_PAT.search(url):
        return False
    txt = (x.get('original_text') or '').strip()
    return len(txt) < MIN_LEN


def main():
    docs = json.load(open(ALL, encoding='utf-8'))
    before = len(docs)
    print(f'before {before}건')

    removed = [x for x in docs if is_thin_board(x)]
    kept = [x for x in docs if not is_thin_board(x)]
    print(f'제거 대상(plus/bbs board view & 본문<{MIN_LEN}자): {len(removed)}건')

    if removed:
        # 카테고리/도메인 통계
        from collections import Counter
        cat = Counter(x.get('data_category', '?') for x in removed)
        dom = Counter()
        for x in removed:
            m = re.match(r'https?://([^/]+)', x.get('source_url') or '')
            if m:
                dom[m.group(1)] += 1
        print('  카테고리:')
        for k, v in cat.most_common():
            print(f'    {v:>4}  {k}')
        print('  도메인:')
        for k, v in dom.most_common():
            print(f'    {v:>4}  {k}')
        print('  샘플 5:')
        for x in removed[:5]:
            t = (x.get('original_text') or '').replace('\n', '|')[:80]
            print(f'    [{len(x.get("original_text") or "")}자] {x["source_url"][:90]}')
            print(f'        {t}')

    # 백업 + 갱신
    bak = ALL.with_name(f'all_dedup.json.cleanup_bak_{date.today().isoformat()}')
    if ALL.exists() and not bak.exists():
        shutil.copy(ALL, bak)
    with open(ALL, 'w', encoding='utf-8') as f:
        json.dump(kept, f, ensure_ascii=False, indent=2)
    print(f'\n저장: {len(kept)}건 (백업 {bak.name})')
    print(f'before {before} → after {len(kept)}  (제거 {before - len(kept)})')


if __name__ == '__main__':
    main()
