"""staging 신규 크롤 → 품질게이트 → title-hash 빠른 dedup → all_dedup 통합 → 리포트+리뷰샘플.

요청 구조(풀 게이트):
  1) COUNT : 통합 전/후 카테고리 분포
  2) DEDUP : title 정규화 해시 + source_url 로 빠른 중복제거 (기존 우선)
  3) QUALITY: 길이<120 / 모지바케(FFFD>1%) / 메뉴잡음 / 한글비율<15% 제거
  4) REVIEW : 카테고리별 샘플 추출 → data/crawled_staging/_review_sample.json
              (리뷰어 에이전트가 별도 검수)

신규 staging만 통합: --since-min N (기본 240분) 안에 수정된 *.json (밑줄/done 제외).
백업: all_dedup.json.iv_bak_{날짜}. 벡터DB는 GPU 서버에서 별도 재빌드(여기선 안 건드림).

실행: python scripts/integrate_verify.py [--since-min 240] [--apply]
       --apply 없으면 dry-run(리포트만, 파일 안 바꿈).
"""
import sys, os, json, re, time, shutil, hashlib, random
from pathlib import Path
from datetime import date

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

ALL = ROOT / 'data' / 'crawled' / 'all_dedup.json'
STAGE = ROOT / 'data' / 'crawled_staging'
REPORT = STAGE / '_integrate_report.json'
SAMPLE = STAGE / '_review_sample.json'

UNDERWEIGHT = {'A_dining', 'A_shuttle', 'A_library', 'E_career', 'D_scholarship',
               'G_dormitory', 'G_student_life', 'G_general', 'H_facilities', 'J_extracurricular'}

# 리뷰어 REJECT 근거: 혼합 포털 BFS는 seed 카테고리를 모든 링크에 도장찍어
# 오분류 ~50%. 전용 URL 재분류 전까지 격리(통합 보류).
QUARANTINE_HOSTS = {'plus.cnu.ac.kr'}


def norm_title(t):
    return re.sub(r'\s+', '', (t or '').lower())[:60]


def body_key(text):
    """본문 정규화 prefix 해시. URL만 다른 동일 메뉴덤프(near-dup) 탐지용."""
    norm = re.sub(r'\s+', '', (text or ''))[:180]
    return hashlib.md5(norm.encode('utf-8')).hexdigest() if norm else None


def hangul_ratio(s):
    if not s:
        return 0.0
    h = sum(1 for c in s if '가' <= c <= '힣')
    return h / len(s)


def fffd_ratio(s):
    if not s:
        return 0.0
    return s.count('�') / len(s)


def is_menu_noise(body):
    lines = [l.strip() for l in (body or '').split('\n') if l.strip()]
    if len(lines) < 5:
        return False
    return sum(1 for l in lines if len(l) < 10) / len(lines) > 0.6


def quality_reason(doc):
    """통과면 None, 탈락이면 사유 문자열."""
    t = (doc.get('original_text') or '').strip()
    if len(t) < 120:
        return 'too_short'
    if fffd_ratio(t) > 0.01:
        return 'mojibake'
    if hangul_ratio(t) < 0.15:
        return 'low_hangul'
    if is_menu_noise(t):
        return 'menu_noise'
    return None


def cat_dist(docs):
    d = {}
    for x in docs:
        c = x.get('data_category', '?')
        d[c] = d.get(c, 0) + 1
    return dict(sorted(d.items()))


def main():
    since_min = 240
    apply = '--apply' in sys.argv
    if '--since-min' in sys.argv:
        since_min = int(sys.argv[sys.argv.index('--since-min') + 1])
    cutoff = time.time() - since_min * 60

    old = json.load(open(ALL, encoding='utf-8'))
    before = cat_dist(old)
    print(f'기존 all_dedup: {len(old)}건')

    # 신규 staging 로드
    new_docs, files = [], []
    for fn in sorted(os.listdir(STAGE)):
        if not fn.endswith('.json') or fn.startswith('_'):
            continue
        p = STAGE / fn
        if p.stat().st_mtime < cutoff:
            continue
        try:
            docs = json.load(open(p, encoding='utf-8'))
        except Exception:
            continue
        files.append((fn, len(docs)))
        new_docs.extend(docs)
    print(f'신규 staging({since_min}분내) {len(files)}파일, {len(new_docs)}건')
    for fn, n in files:
        print(f'  {fn}: {n}')

    # 기존 인덱스 (dedup 기준) — title/url + 본문 near-dup(메뉴덤프 차단)
    seen_title = {norm_title(x.get('title')) for x in old}
    seen_url = {x.get('source_url') for x in old}
    seen_body = {body_key(x.get('original_text')) for x in old}
    seen_body.discard(None)

    kept, dropped, quarantined = [], [], []
    drop_q, drop_dup, drop_body, q_reasons = 0, 0, 0, {}
    seen_new_t, seen_new_u = set(), set()
    for d in new_docs:
        host = re.sub(r'^https?://([^/]+).*', r'\1', d.get('source_url', '') or '')
        if host in QUARANTINE_HOSTS:
            quarantined.append(d)
            continue
        r = quality_reason(d)
        if r:
            drop_q += 1
            q_reasons[r] = q_reasons.get(r, 0) + 1
            dropped.append({'reason': r, 'cat': d.get('data_category'),
                            'title': d.get('title', ''), 'url': d.get('source_url', ''),
                            'head': (d.get('original_text') or '')[:200]})
            continue
        nt, nu, bk = norm_title(d.get('title')), d.get('source_url'), body_key(d.get('original_text'))
        if nt in seen_title or nu in seen_url or nt in seen_new_t or nu in seen_new_u:
            drop_dup += 1
            continue
        if bk and bk in seen_body:   # 본문 동일(URL만 다른 메뉴덤프 등)
            drop_body += 1
            dropped.append({'reason': 'body_dup', 'cat': d.get('data_category'),
                            'title': d.get('title', ''), 'url': d.get('source_url', ''),
                            'head': (d.get('original_text') or '')[:200]})
            continue
        seen_new_t.add(nt)
        seen_new_u.add(nu)
        if bk:
            seen_body.add(bk)
        kept.append(d)

    if quarantined:
        json.dump(quarantined, open(STAGE / '_quarantine.json', 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=2)
    print(f'\n격리(plus.cnu 오분류) {len(quarantined)} → _quarantine.json (재태깅 대기)')
    print(f'품질탈락 {drop_q} {q_reasons} | title/url중복 {drop_dup} | '
          f'본문near-dup {drop_body} | 신규채택 {len(kept)}')

    merged = old + kept
    after = cat_dist(merged)

    # COUNT 리포트: 빈약 카테고리 변화 강조
    print('\n=== 카테고리 변화 (빈약 카테고리) ===')
    for c in sorted(set(before) | set(after)):
        b, a = before.get(c, 0), after.get(c, 0)
        if a != b or c in UNDERWEIGHT:
            mark = ' <<' if c in UNDERWEIGHT else ''
            print(f'  {c:18s} {b:5d} -> {a:5d}  (+{a-b}){mark}')

    # REVIEW 샘플: 신규채택분에서 카테고리별 최대 3건
    by_cat = {}
    for d in kept:
        by_cat.setdefault(d.get('data_category', '?'), []).append(d)
    sample = []
    for c, ds in by_cat.items():
        for d in random.Random(42).sample(ds, min(3, len(ds))):
            sample.append({'data_category': c, 'title': d.get('title', ''),
                           'source_url': d.get('source_url', ''),
                           'text_head': (d.get('original_text') or '')[:500],
                           'len': len(d.get('original_text') or ''),
                           'hangul_ratio': round(hangul_ratio(d.get('original_text')), 2)})

    report = {'before_total': len(old), 'after_total': len(merged),
              'new_kept': len(kept), 'drop_quality': drop_q,
              'drop_quality_reasons': q_reasons, 'drop_dup': drop_dup,
              'drop_body_dup': drop_body,
              'files': files, 'before': before, 'after': after,
              'underweight_after': {c: after.get(c, 0) for c in sorted(UNDERWEIGHT)}}
    json.dump(report, open(REPORT, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    json.dump(sample, open(SAMPLE, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    # 드롭 문서 보존(감사용): 사유별 최대 12건
    drop_sample, by_reason = [], {}
    for x in dropped:
        by_reason.setdefault(x['reason'], []).append(x)
    for rsn, xs in by_reason.items():
        drop_sample.extend(xs[:12])
    json.dump(drop_sample, open(STAGE / '_dropped_sample.json', 'w', encoding='utf-8'),
              ensure_ascii=False, indent=2)
    print(f'\n리포트 → {REPORT}\n리뷰샘플({len(sample)}건) → {SAMPLE}'
          f'\n드롭샘플({len(drop_sample)}건) → {STAGE / "_dropped_sample.json"}')

    if apply:
        bak = str(ALL) + f'.iv_bak_{date.today().isoformat()}'
        shutil.copy(str(ALL), bak)
        json.dump(merged, open(ALL, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
        print(f'\n적용완료. 백업 {bak}\nall_dedup: {len(old)} -> {len(merged)}')
    else:
        print('\n[dry-run] --apply 붙이면 실제 통합. 지금은 리포트만.')


if __name__ == '__main__':
    main()
