"""재태깅 스크립트: _quarantine.json 516건을 URL 경로 + 본문 키워드로 올바른 카테고리로 재태깅.

DRY-RUN: _retagged.json 산출 + 콘솔 리포트. _quarantine.json / all_dedup.json 수정 금지.
실행: python scripts/retag_quarantine.py
"""
import sys, os, json, re, hashlib
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

QUARANTINE = ROOT / 'data' / 'crawled_staging' / '_quarantine.json'
OUT_RETAGGED = ROOT / 'data' / 'crawled_staging' / '_retagged.json'

# ---------------------------------------------------------------------------
# 분류 규칙 (우선순위 순서: 위일수록 우선)
# 각 항목: (category_id, url_keywords, text_keywords)
# ---------------------------------------------------------------------------
RULES = [
    # 구체적 카테고리 먼저
    ("D_scholarship",   ["scholarship", "janghakg", "0713", "jangha"],
                        ["장학", "등록금", "학자금", "장학금", "수혜", "국가장학"]),

    ("A_shuttle",       ["shuttle", "bus", "mobileadmin.*shuttle", "shuttle"],
                        ["셔틀", "통학버스", "통학 버스", "교통편", "버스 노선"]),

    ("E_career",        ["job", "career", "recruit", "intern", "employment"],
                        ["취업", "진로", "채용", "인턴", "취업지원", "구인", "채용공고"]),

    ("G_dormitory",     ["dorm", "dormitory", "student.*house", "residence"],
                        ["기숙사", "생활관", "기숙", "dormitory"]),

    ("B_academic",      ["academic", "course", "grade", "curriculum", "sugang", "haksа"],
                        ["학사", "수강", "졸업", "학점", "성적", "수업", "교과목", "이수",
                         "수강신청", "강의", "시간표"]),

    ("C_administration",["admin", "certificate", "registration", "payment", "fee", "tuition",
                         "finance"],
                        ["증명", "행정", "민원", "재무", "납부", "등록", "납입", "고지서",
                         "서류", "증명서 발급"]),

    ("I_international", ["international", "exchange", "global", "study.*abroad", "overseas"],
                        ["국제", "교환학생", "유학", "해외", "외국인 유학생"]),

    ("A_library",       ["library", "libr", "book"],
                        ["도서관", "열람실", "열람", "도서", "서고"]),

    ("J_extracurricular",["club", "volunteer", "extracurr", "noncurr"],
                        ["동아리", "학생회", "비교과", "봉사", "대외활동", "써클"]),

    # 가장 넓은 버킷을 마지막에
    ("G_student_life",  ["student", "stuserv", "life"],
                        ["학생", "학생생활", "복지", "상담", "보건", "의료"]),
]

# ---------------------------------------------------------------------------
# 품질 게이트 (integrate_verify.py 동일 기준)
# ---------------------------------------------------------------------------

def hangul_ratio(s: str) -> float:
    if not s:
        return 0.0
    h = sum(1 for c in s if '가' <= c <= '힣')
    return h / len(s)

def fffd_ratio(s: str) -> float:
    if not s:
        return 0.0
    return s.count('�') / len(s)

def is_menu_noise(body: str) -> bool:
    lines = [l.strip() for l in (body or '').split('\n') if l.strip()]
    if len(lines) < 5:
        return False
    return sum(1 for l in lines if len(l) < 10) / len(lines) > 0.6

def quality_reason(doc: dict):
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

# ---------------------------------------------------------------------------
# Near-dup (prefix-180 해시)
# ---------------------------------------------------------------------------

def body_key(text: str):
    norm = re.sub(r'\s+', '', (text or ''))[:180]
    return hashlib.md5(norm.encode('utf-8')).hexdigest() if norm else None

# ---------------------------------------------------------------------------
# 카테고리 분류
# ---------------------------------------------------------------------------

def classify(url: str, text: str, title: str) -> str | None:
    """올바른 카테고리 반환. 매칭 없으면 None (드롭)."""
    combined_url = url.lower()
    combined_text = ((text or '') + ' ' + (title or '')).lower()

    for cat_id, url_kws, text_kws in RULES:
        url_hit = any(re.search(kw, combined_url) for kw in url_kws)
        text_hit = any(kw in combined_text for kw in text_kws)
        if url_hit or text_hit:
            return cat_id
    return None  # 드롭


def main():
    docs = json.load(open(QUARANTINE, encoding='utf-8'))
    print(f'격리분 로드: {len(docs)}건')

    retagged = []
    dropped_no_match = []
    dropped_quality = []
    quality_reasons_count: dict[str, int] = {}
    cat_dist: dict[str, int] = defaultdict(int)

    seen_body: set[str] = set()
    neardup_removed = 0

    for doc in docs:
        url = doc.get('source_url', '')
        text = doc.get('original_text', '')
        title = doc.get('title', '')

        # 1) 카테고리 분류
        new_cat = classify(url, text, title)
        if new_cat is None:
            dropped_no_match.append(doc)
            continue

        # 2) 품질 게이트
        reason = quality_reason(doc)
        if reason:
            quality_reasons_count[reason] = quality_reasons_count.get(reason, 0) + 1
            dropped_quality.append(doc)
            continue

        # 3) near-dup
        bk = body_key(text)
        if bk and bk in seen_body:
            neardup_removed += 1
            continue
        if bk:
            seen_body.add(bk)

        # 통과
        new_doc = dict(doc)
        new_doc['data_category'] = new_cat
        new_doc['_retagged_from'] = doc.get('data_category', '')
        retagged.append(new_doc)
        cat_dist[new_cat] += 1

    # ---------------------------------------------------------------------------
    # 출력
    # ---------------------------------------------------------------------------
    total_dropped = len(dropped_no_match) + len(dropped_quality) + neardup_removed
    print(f'\n[재태깅 결과]')
    print(f'  재태깅 통과: {len(retagged)}건')
    print(f'  드롭(매칭없음): {len(dropped_no_match)}건')
    print(f'  드롭(품질게이트): {len(dropped_quality)}건 {quality_reasons_count}')
    print(f'  near-dup 제거: {neardup_removed}건')
    print(f'  총 드롭: {total_dropped}건')

    print(f'\n[재태깅 카테고리 분포]')
    for cat, cnt in sorted(cat_dist.items(), key=lambda x: -x[1]):
        print(f'  {cat:22s}: {cnt:4d}건')

    print(f'\n[카테고리별 샘플 2건 (제목 + 앞150자 + 한글코드포인트수)]')
    by_cat: dict[str, list] = defaultdict(list)
    for d in retagged:
        by_cat[d['data_category']].append(d)

    for cat in sorted(by_cat.keys()):
        samples = by_cat[cat][:2]
        print(f'\n  [{cat}]')
        for s in samples:
            t = s.get('original_text', '')
            head = t[:150]
            ko_count = sum(1 for c in t if '가' <= c <= '힣')
            title_disp = (s.get('title') or '')[:60]
            print(f'    제목: {title_disp}')
            print(f'    본문앞150: {repr(head)}')
            print(f'    한글코드포인트수: {ko_count}')

    # 산출 파일 저장
    json.dump(retagged, open(OUT_RETAGGED, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=2)
    print(f'\n산출 -> {OUT_RETAGGED} ({len(retagged)}건)')


if __name__ == '__main__':
    main()
