"""콘텐츠 이미지 → Gemini Vision OCR → 텍스트 추출 → 매핑에 반영.

content_images/_mapping.json 의 각 이미지를 Gemini 2.5 Flash로 한국어 텍스트 추출.
결과를 extracted_text로 매핑에 저장 + (옵션) 해당 문서 all_dedup에 보강.

전제: GEMINI_API_KEY 환경변수 (채팅에 붙이지 말 것).
실행:
  export GEMINI_API_KEY=...        # 터미널 env로만
  python scripts/ocr_images_gemini.py
"""
import sys, os, json, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

IMG_DIR = ROOT / 'data' / 'content_images'
MAP = IMG_DIR / '_mapping.json'
MODEL = os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash')

PROMPT = ("이 이미지에 담긴 텍스트 정보(메뉴·가격·안내·표·공지·교육목표 등)를 "
          "한국어로 빠짐없이 추출하세요. 표는 '항목: 값' 형태로 풀어서. "
          "이미지 설명이나 해설은 빼고, 담긴 내용 텍스트만 출력하세요.")

MIME = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png', 'gif': 'image/gif'}


def main():
    key = os.environ.get('GEMINI_API_KEY', '').strip()
    if not key:
        print('[에러] GEMINI_API_KEY 환경변수 없음. export GEMINI_API_KEY=... 후 실행.')
        sys.exit(1)
    if not MAP.exists():
        print(f'[에러] {MAP} 없음. collect_content_images.py 먼저 실행.')
        sys.exit(1)

    from google import genai
    from google.genai import types
    client = genai.Client(api_key=key)

    m = json.load(open(MAP, encoding='utf-8'))
    print(f'이미지 {len(m)}개 OCR 시작 (모델 {MODEL})', flush=True)
    ok = 0
    for i, item in enumerate(m):
        if item.get('extracted_text'):  # resume
            ok += 1
            continue
        p = IMG_DIR / item['image']
        if not p.exists():
            continue
        ext = item['image'].rsplit('.', 1)[-1].lower()
        try:
            resp = client.models.generate_content(
                model=MODEL,
                contents=[
                    types.Part.from_bytes(data=p.read_bytes(),
                                          mime_type=MIME.get(ext, 'image/jpeg')),
                    PROMPT,
                ],
            )
            txt = (resp.text or '').strip()
            item['extracted_text'] = txt
            ok += 1
            print(f'  [{i+1}/{len(m)}] {item["title"][:30]} → {len(txt)}자', flush=True)
        except Exception as e:
            item['extracted_text'] = ''
            print(f'  [{i+1}/{len(m)}] 실패: {e}', flush=True)
        time.sleep(0.3)
        json.dump(m, open(MAP, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

    print(f'\n완료: {ok}/{len(m)} 추출. → {MAP}', flush=True)
    print('  extracted_text 필드에 저장됨. all_dedup 반영은 별도 단계.', flush=True)


if __name__ == '__main__':
    main()
