"""OCR 본문 반영 (DRY-RUN 기본 / --apply 로 실제 반영).

_mapping.json 의 extracted_text(Gemini+EasyOCR) 를 source_doc URL 이 일치하는
all_dedup.json 문서의 본문(original_text/content)에 append.

OCR 품질 게이트:
  - 한글 코드포인트 < 15 → 스킵
  - 로고 텍스트 패턴 ('STRONG CNU', 'MEGA UNIVERSITY', 'CNU LIBRARY' 등) → 스킵

반영 정책:
  - 빈약문서(original_text < 200자) 위주로만 본문에 append.
  - 중복 append 방지: 이미 같은 OCR 텍스트가 본문에 들어가 있으면(또는 [OCR]
    마커가 이미 있으면) 스킵.
  - 반영 시 original_text 와 content 둘 다 갱신(파이프라인 청킹은 original_text 사용).

실행:
  python scripts/reflect_ocr.py            # DRY-RUN(집계만, 파일 미수정)
  python scripts/reflect_ocr.py --apply    # 실제 반영(백업 *.ocr_bak_날짜 후 적용)
  python scripts/reflect_ocr.py --apply --all-len   # 길이 무관 전체 매칭분 반영
"""
import sys, json, re, shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

MAPPING = ROOT / 'data' / 'content_images' / '_mapping.json'
ALL_DEDUP = ROOT / 'data' / 'crawled' / 'all_dedup.json'

# 빈약문서 기준(이 길이 미만이면 OCR 보강 대상)
WEAK_DOC_MAXLEN = 200
# 본문에 붙이는 OCR 마커(중복 append 방지 키 겸용)
OCR_MARKER = '[OCR]'

# 로고 텍스트 패턴 (대소문자 무관)
LOGO_PATTERNS = [
    r'STRONG\s+CNU',
    r'MEGA\s+UNIVERSITY',
    r'CNU\s+LIBRARY',
    r'CHUNGNAM\s+NATIONAL\s+UNIVERSITY',
]
LOGO_RE = re.compile('|'.join(LOGO_PATTERNS), re.IGNORECASE)


def hangul_count(s: str) -> int:
    return sum(1 for c in s if '가' <= c <= '힣')


def ocr_quality_pass(text: str) -> bool:
    """품질 게이트 통과하면 True."""
    if not text or not text.strip():
        return False
    if hangul_count(text) < 15:
        return False
    if LOGO_RE.search(text):
        return False
    return True


def collect_valid_ocr(mapping):
    """mapping 에서 품질 게이트 통과 항목만 추림. (valid, 스킵카운트)."""
    valid_ocr = []
    skipped_logo = skipped_no_hangul = skipped_empty = 0
    for entry in mapping:
        text = entry.get('extracted_text', '') or ''
        if not text.strip():
            skipped_empty += 1
            continue
        if LOGO_RE.search(text):
            skipped_logo += 1
            continue
        if hangul_count(text) < 15:
            skipped_no_hangul += 1
            continue
        valid_ocr.append(entry)
    return valid_ocr, skipped_logo, skipped_no_hangul, skipped_empty


def build_url_index(all_dedup):
    """source_url → doc index. 같은 URL 이 여러 문서면 마지막 것이 우선(덮어쓰기)."""
    url_index = {}
    for i, doc in enumerate(all_dedup):
        url = doc.get('source_url', '')
        if url:
            url_index[url] = i
    return url_index


def main():
    apply = '--apply' in sys.argv
    all_len = '--all-len' in sys.argv  # 길이 무관 전체 매칭분 반영

    mapping = json.load(open(MAPPING, encoding='utf-8'))
    all_dedup = json.load(open(ALL_DEDUP, encoding='utf-8'))

    print(f'_mapping.json 총 항목: {len(mapping)}건')
    print(f'all_dedup.json 총 문서: {len(all_dedup)}건')
    print(f'모드: {"APPLY(실제 반영)" if apply else "DRY-RUN(집계만)"}'
          f'{"  (길이무관 전체)" if all_len else f"  (빈약문서<{WEAK_DOC_MAXLEN}자 위주)"}')

    valid_ocr, skipped_logo, skipped_no_hangul, skipped_empty = collect_valid_ocr(mapping)
    print(f'\n[OCR 품질 게이트]')
    print(f'  유효(통과):      {len(valid_ocr)}건')
    print(f'  스킵(로고텍스트): {skipped_logo}건')
    print(f'  스킵(한글<15):   {skipped_no_hangul}건')
    print(f'  스킵(비어있음):   {skipped_empty}건')

    url_index = build_url_index(all_dedup)

    matched = []        # 매칭 성공(빈약/전체 필터 적용 전)
    unmatched = []
    target = []         # 실제 반영 대상(필터 통과 + 중복 아님)
    skipped_dup = 0     # 이미 반영되어 스킵
    skipped_len = 0     # 빈약문서 아니라 스킵(--all-len 아닐 때)
    before_after = []   # (orig_len, new_len) 실제 반영분

    for entry in valid_ocr:
        source_doc = entry.get('source_doc', '') or ''
        ocr_text = (entry.get('extracted_text', '') or '').strip()

        if source_doc not in url_index:
            unmatched.append(entry)
            continue

        idx = url_index[source_doc]
        doc = all_dedup[idx]
        orig_text = doc.get('original_text', '') or ''
        orig_len = len(orig_text)

        matched.append({
            'idx': idx, 'source_doc': source_doc, 'title': doc.get('title', ''),
            'orig_len': orig_len, 'ocr_added': len(ocr_text), 'ocr_head': ocr_text[:100],
        })

        # 빈약문서 필터(--all-len 이면 길이 무관)
        if not all_len and orig_len >= WEAK_DOC_MAXLEN:
            skipped_len += 1
            continue

        # 중복 append 방지: 이미 같은 OCR 텍스트가 본문에 있거나 마커가 있으면 스킵
        if ocr_text and ocr_text in orig_text:
            skipped_dup += 1
            continue

        target.append({'idx': idx, 'ocr_text': ocr_text, 'orig_len': orig_len,
                        'title': doc.get('title', '')})

    print(f'\n[매칭 결과]')
    print(f'  OCR유효: {len(valid_ocr)}건  /  매칭성공: {len(matched)}건  /  매칭실패: {len(unmatched)}건')
    weak_cnt = sum(1 for m in matched if m['orig_len'] < WEAK_DOC_MAXLEN)
    print(f'  빈약문서(원문<{WEAK_DOC_MAXLEN}자) 매칭: {weak_cnt}건')
    print(f'  반영 대상(필터+중복제거 후): {len(target)}건')
    print(f'  스킵(길이초과): {skipped_len}건  /  스킵(이미 반영됨): {skipped_dup}건')

    if not apply:
        avg_added = int(sum(t['ocr_text'].__len__() for t in target) / len(target)) if target else 0
        print(f'  [DRY-RUN] 반영 시 평균증가글자수: {avg_added}자')
        print(f'\n[샘플 3건: 문서제목 + 기존길이 + OCR추가텍스트 앞80자 + 한글코드포인트]')
        for t in target[:3]:
            print(f'\n  제목:        {t["title"][:70]}')
            print(f'  기존길이:    {t["orig_len"]}자')
            print(f'  OCR추가(앞80): {t["ocr_text"][:80]!r}')
            print(f'  한글코드포인트: {hangul_count(t["ocr_text"])}')
        print(f'\n[최종 요약/DRY-RUN] 유효 {len(valid_ocr)} / 매칭 {len(matched)} / '
              f'반영대상 {len(target)} / 평균증가 {avg_added}자')
        print('\n실제 반영하려면:  python scripts/reflect_ocr.py --apply')
        return

    # ---- APPLY ----
    if not target:
        print('\n[APPLY] 반영 대상이 0건이라 파일을 수정하지 않습니다(이미 반영됐거나 매칭 없음).')
        return

    # 백업
    stamp = datetime.now().strftime('%Y%m%d')
    bak = ALL_DEDUP.with_name(ALL_DEDUP.name + f'.ocr_bak_{stamp}')
    if not bak.exists():
        shutil.copy2(ALL_DEDUP, bak)
        print(f'\n[APPLY] 백업 생성: {bak}')
    else:
        print(f'\n[APPLY] 백업 이미 존재(보존): {bak}')

    total_before = total_after = 0
    samples = []
    for t in target:
        doc = all_dedup[t['idx']]
        orig = doc.get('original_text', '') or ''
        appended = f"\n\n{OCR_MARKER} {t['ocr_text']}"
        new_text = orig + appended
        doc['original_text'] = new_text
        # content 가 original_text 를 미러링하던 문서면 같이 갱신, 아니면 content 에도 동일 append
        doc['content'] = (doc.get('content', '') or '') + appended
        total_before += len(orig)
        total_after += len(new_text)
        if len(samples) < 3:
            samples.append((doc.get('title', ''), t['ocr_text'], hangul_count(t['ocr_text'])))

    with open(ALL_DEDUP, 'w', encoding='utf-8') as f:
        json.dump(all_dedup, f, ensure_ascii=False, indent=2)

    n = len(target)
    avg_inc = int((total_after - total_before) / n) if n else 0
    print(f'[APPLY] 반영 완료: {n}개 문서')
    print(f'  반영 전 합계글자: {total_before}자  →  반영 후 합계글자: {total_after}자')
    print(f'  평균 증가글자: {avg_inc}자/문서')
    print(f'  저장: {ALL_DEDUP}')

    print(f'\n[샘플 3건: 문서제목 + 추가된 OCR텍스트 앞80자 + 한글코드포인트]')
    for title, ocr, ko in samples:
        print(f'\n  제목:        {title[:70]}')
        print(f'  OCR추가(앞80): {ocr[:80]!r}')
        print(f'  한글코드포인트: {ko}')


if __name__ == '__main__':
    main()
