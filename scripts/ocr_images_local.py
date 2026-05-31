"""로컬 EasyOCR 기반 콘텐츠 이미지 한국어 텍스트 추출.

data/content_images/_mapping.json 의 각 이미지를 EasyOCR(ko+en, CPU)로 처리.
이미 extracted_text 가 있으면 건너뜀(resume).
매 SAVE_EVERY 건마다 중간 저장.

실행:
  python scripts/ocr_images_local.py
"""
import sys
import os
import json
import logging
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
IMG_DIR = ROOT / 'data' / 'content_images'
MAP = IMG_DIR / '_mapping.json'
LOG_FILE = ROOT / 'data' / 'planner' / 'ocr_local.log'

SAVE_EVERY = 10  # N건마다 중간 저장


def setup_logger():
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger('ocr_local')
    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    fh = logging.FileHandler(str(LOG_FILE), encoding='utf-8')
    fh.setFormatter(fmt)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(sh)
    return logger


def main():
    log = setup_logger()

    if not MAP.exists():
        log.error(f'{MAP} 없음. collect_content_images.py 먼저 실행.')
        sys.exit(1)

    log.info('EasyOCR 초기화 중 (첫 실행 시 모델 다운로드, 시간 소요)...')
    try:
        import easyocr
    except ImportError:
        log.error('easyocr 미설치. pip install easyocr 후 재실행.')
        sys.exit(1)

    reader = easyocr.Reader(['ko', 'en'], gpu=False)
    log.info('EasyOCR reader 준비 완료.')

    with open(MAP, encoding='utf-8') as f:
        m = json.load(f)

    total = len(m)
    log.info(f'이미지 {total}개 OCR 시작')

    ok = 0
    skipped = 0
    failed = 0
    unsaved_count = 0

    for i, item in enumerate(m):
        # resume: 이미 추출된 항목 건너뜀
        if item.get('extracted_text', '').strip():
            ok += 1
            skipped += 1
            continue

        img_path = IMG_DIR / item['image']
        if not img_path.exists():
            log.warning(f'[{i+1}/{total}] 파일 없음: {item["image"]}')
            item['extracted_text'] = ''
            failed += 1
            unsaved_count += 1
        else:
            try:
                results = reader.readtext(str(img_path), detail=0)
                txt = '\n'.join(results).strip()
                item['extracted_text'] = txt
                ok += 1
                unsaved_count += 1
                title_preview = item.get('title', '')[:30]
                log.info(f'[{i+1}/{total}] {title_preview} -> {len(txt)}자')
            except Exception as e:
                item['extracted_text'] = ''
                failed += 1
                unsaved_count += 1
                log.warning(f'[{i+1}/{total}] 실패 {item["image"]}: {e}')

        # 중간 저장
        if unsaved_count >= SAVE_EVERY:
            with open(MAP, 'w', encoding='utf-8') as f:
                json.dump(m, f, ensure_ascii=False, indent=2)
            log.info(f'  중간 저장 ({i+1}/{total})')
            unsaved_count = 0

    # 최종 저장
    with open(MAP, 'w', encoding='utf-8') as f:
        json.dump(m, f, ensure_ascii=False, indent=2)

    newly_extracted = ok - skipped
    log.info(f'\n=== 완료 ===')
    log.info(f'전체: {total}건 | 기존 보유: {skipped}건 | 신규 추출: {newly_extracted}건 | 실패: {failed}건')
    log.info(f'저장 위치: {MAP}')

    # 통계 집계
    texts = [item.get('extracted_text', '') for item in m if item.get('extracted_text', '').strip()]
    if texts:
        avg_len = sum(len(t) for t in texts) / len(texts)
        korean_count = sum(1 for t in texts if any('가' <= c <= '힣' for c in t))
        korean_ratio = korean_count / len(texts) * 100
        log.info(f'추출 성공: {len(texts)}건 | 평균 글자수: {avg_len:.1f} | 한글 포함 비율: {korean_ratio:.1f}%')

        # 샘플 3건 출력
        log.info('\n--- 샘플 3건 ---')
        sample_items = [item for item in m if item.get('extracted_text', '').strip()][:3]
        for item in sample_items:
            txt = item.get('extracted_text', '')
            ko_chars = sum(1 for c in txt if '가' <= c <= '힣')
            preview = txt[:100]
            log.info(f'title: {item.get("title", "")}')
            log.info(f'  텍스트 앞100자: {preview}')
            log.info(f'  한글 코드포인트 수: {ko_chars}')

    return {
        'total': total,
        'skipped': skipped,
        'newly_extracted': newly_extracted,
        'failed': failed,
        'texts_with_content': len(texts) if texts else 0,
        'avg_len': avg_len if texts else 0,
        'korean_ratio': korean_ratio if texts else 0,
    }


if __name__ == '__main__':
    main()
