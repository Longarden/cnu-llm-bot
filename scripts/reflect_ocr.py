"""OCR 본문 반영 시뮬레이션 (DRY-RUN).

_mapping.json 의 extracted_text 를 all_dedup.json 문서에 반영하면 어떻게 되는지만 집계.
all_dedup.json 원본 수정 금지.

OCR 품질 게이트:
  - 한글 코드포인트 < 15 → 스킵
  - 로고 텍스트 패턴 ('STRONG CNU', 'MEGA UNIVERSITY', 'CNU LIBRARY' 등) → 스킵

실행: python scripts/reflect_ocr.py
"""
import sys, json, re
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

MAPPING = ROOT / 'data' / 'content_images' / '_mapping.json'
ALL_DEDUP = ROOT / 'data' / 'crawled' / 'all_dedup.json'

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
    ko = hangul_count(text)
    if ko < 15:
        return False
    if LOGO_RE.search(text):
        return False
    return True


def main():
    mapping = json.load(open(MAPPING, encoding='utf-8'))
    all_dedup = json.load(open(ALL_DEDUP, encoding='utf-8'))

    print(f'_mapping.json 총 항목: {len(mapping)}건')
    print(f'all_dedup.json 총 문서: {len(all_dedup)}건')

    # OCR 품질 게이트 적용
    valid_ocr = []
    skipped_logo = 0
    skipped_no_hangul = 0
    skipped_empty = 0

    for entry in mapping:
        text = entry.get('extracted_text', '') or ''
        if not text.strip():
            skipped_empty += 1
            continue
        ko = hangul_count(text)
        if LOGO_RE.search(text):
            skipped_logo += 1
            continue
        if ko < 15:
            skipped_no_hangul += 1
            continue
        valid_ocr.append(entry)

    print(f'\n[OCR 품질 게이트]')
    print(f'  유효(통과):      {len(valid_ocr)}건')
    print(f'  스킵(로고텍스트): {skipped_logo}건')
    print(f'  스킵(한글<15):   {skipped_no_hangul}건')
    print(f'  스킵(비어있음):   {skipped_empty}건')

    # all_dedup URL 인덱스 (source_url → doc index)
    url_index: dict[str, int] = {}
    for i, doc in enumerate(all_dedup):
        url = doc.get('source_url', '')
        if url:
            url_index[url] = i

    # 매칭 및 시뮬레이션
    matched = []
    unmatched = []
    weak_doc_boosted = 0  # 원문 < 200자 문서 중 보강되는 건수
    added_chars_list = []

    for entry in valid_ocr:
        source_doc = entry.get('source_doc', '') or ''
        ocr_text = entry.get('extracted_text', '') or ''

        if source_doc in url_index:
            idx = url_index[source_doc]
            doc = all_dedup[idx]
            orig_text = doc.get('original_text', '') or ''
            orig_len = len(orig_text)
            added = len(ocr_text)
            added_chars_list.append(added)

            if orig_len < 200:
                weak_doc_boosted += 1

            matched.append({
                'source_doc': source_doc,
                'title': doc.get('title', ''),
                'orig_len': orig_len,
                'ocr_added': added,
                'ocr_head': ocr_text[:100],
            })
        else:
            unmatched.append(entry)

    avg_added = int(sum(added_chars_list) / len(added_chars_list)) if added_chars_list else 0

    print(f'\n[매칭 결과]')
    print(f'  OCR유효: {len(valid_ocr)}건')
    print(f'  매칭성공: {len(matched)}건')
    print(f'  매칭실패: {len(unmatched)}건')
    print(f'  빈약문서(원문<200자) 보강 대상: {weak_doc_boosted}건')
    print(f'  반영시 평균증가글자수: {avg_added}자')

    print(f'\n[샘플 3건: 문서제목 + 기존길이 + OCR추가텍스트 앞100자]')
    for s in matched[:3]:
        print(f'\n  제목:        {s["title"][:70]}')
        print(f'  기존길이:    {s["orig_len"]}자')
        print(f'  OCR추가(앞100): {repr(s["ocr_head"])}')

    # 매칭 실패 URL 샘플 (진단용)
    if unmatched:
        print(f'\n[매칭실패 샘플 3건 source_doc]')
        for e in unmatched[:3]:
            print(f'  {e.get("source_doc", "")}')

    print(f'\n[최종 요약]')
    print(f'  OCR유효 {len(valid_ocr)} / 매칭성공 {len(matched)} / '
          f'빈약문서보강 {weak_doc_boosted} / 평균증가글자 {avg_added}자')


if __name__ == '__main__':
    main()
