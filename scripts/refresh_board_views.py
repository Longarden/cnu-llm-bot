"""게시판 view URL 행을 강화된 fetch_post(include_attachments=True)로 다시 페치해 본문 교체.

조건:
  - source_url 이 게시판 view 패턴 (plus _prog/_board, library/cnustudent /bbs/, computer notice?mode=view 등)
  - 새 본문이 의미있게 더 풍부할 때만 교체
      교체 기준: new_len > max(old_len * 1.3, old_len + 100)
실행: python scripts/refresh_board_views.py [--dry-run]
출력: data/crawled/all_dedup.json 갱신 + 백업 + 리포트
"""
import sys, json, shutil, re, time
from pathlib import Path
from datetime import date

ROOT = Path('C:/Users/dmsak/cnu-llm-bot')
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

from crawler_pipeline.body_extractor import fetch_post

ALL = ROOT / 'data/crawled/all_dedup.json'

# 게시판 view 패턴
VIEW_PATTERNS = [
    re.compile(r'plus\.cnu\.ac\.kr/_prog/_board/'),
    re.compile(r'\.cnu\.ac\.kr/[a-z]+/notice/[a-z]+\.do\?mode=view', re.I),
    re.compile(r'\.cnu\.ac\.kr/bbs/content/'),
    re.compile(r'\.cnu\.ac\.kr/.+\.do\?mode=V'),
]


def is_view(url: str) -> bool:
    if not url:
        return False
    return any(p.search(url) for p in VIEW_PATTERNS)


def should_replace(old_text: str, new_text: str) -> bool:
    old_len = len((old_text or '').strip())
    new_len = len((new_text or '').strip())
    if new_len < 80:
        return False
    threshold = max(int(old_len * 1.3), old_len + 100)
    return new_len > threshold


def main():
    dry = '--dry-run' in sys.argv
    docs = json.load(open(ALL, encoding='utf-8'))
    print(f'base {len(docs)}건')

    targets = [(i, d) for i, d in enumerate(docs) if is_view(d.get('source_url'))]
    print(f'refresh 대상 board view: {len(targets)}건')

    if not targets:
        print('대상 없음')
        return

    stats = {'fetched_ok': 0, 'replaced': 0, 'kept_old': 0, 'fetch_fail': 0}
    log_path = ROOT / 'data/planner/refresh_progress.log'
    log_path.parent.mkdir(parents=True, exist_ok=True)
    lf = open(log_path, 'w', encoding='utf-8')

    for k, (idx, doc) in enumerate(targets, 1):
        url = doc['source_url']
        old = doc.get('original_text') or ''
        res = fetch_post(url, timeout=25, min_len=40, include_attachments=True)
        if not res:
            stats['fetch_fail'] += 1
            lf.write(f'[{k}/{len(targets)}] FAIL {url}\n')
            time.sleep(0.15)
            continue
        stats['fetched_ok'] += 1
        new_text = res.get('text') or ''
        if should_replace(old, new_text):
            stats['replaced'] += 1
            if not dry:
                docs[idx]['original_text'] = new_text
                docs[idx]['content'] = new_text
                if res.get('title'):
                    # 옛 제목이 빈약("게시물 N"등)이면 갱신
                    old_title = doc.get('title') or ''
                    if (not old_title) or re.match(r'^게시물\s*\d+', old_title.strip()):
                        docs[idx]['title'] = res['title']
            lf.write(f'[{k}/{len(targets)}] REPLACED {len(old)}→{len(new_text)}자  {url}\n')
            if k % 20 == 0:
                print(f'  ... {k}/{len(targets)} (replaced so far {stats["replaced"]})', flush=True)
        else:
            stats['kept_old'] += 1
            lf.write(f'[{k}/{len(targets)}] keep ({len(old)}→{len(new_text)})  {url}\n')
        time.sleep(0.12)

    lf.close()
    print('\n=== 결과 ===')
    for k, v in stats.items():
        print(f'  {k:<15} {v}')

    if dry:
        print('(dry-run: 파일 안 건드림)')
        return

    bak = ALL.with_name(f'all_dedup.json.refresh_bak_{date.today().isoformat()}')
    if ALL.exists() and not bak.exists():
        shutil.copy(ALL, bak)
    with open(ALL, 'w', encoding='utf-8') as f:
        json.dump(docs, f, ensure_ascii=False, indent=2)
    print(f'저장: {len(docs)}건 → {ALL.name} (백업 {bak.name})')
    print(f'진행 로그: {log_path}')


if __name__ == '__main__':
    main()
