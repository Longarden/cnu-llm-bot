"""분류기 train 표현증강(빌드타임 Gemini). train.json 질문을 구어체/어순/동의어
변주로 패러프레이즈해 다양성↑ → 실제 test F1 개선. 라벨 보존, valid는 건드리지 않음(누수 방지).

쿼터 절약: 한 Gemini 호출에 여러 질문 배치 → 질문당 N개 패러프레이즈 JSON으로 받음.
전제: GEMINI_API_KEY 환경변수. 실행: python scripts/augment_train_cls.py
출력: data/cls/train_aug.json (원본+증강 합본). 원본 train.json은 보존.
"""
import sys, os, json, re, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

CLS = ROOT / 'data' / 'cls'
MODEL = os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash')
PER_Q = int(os.environ.get('AUG_PER_Q', '3'))     # 질문당 패러프레이즈 수
BATCH = int(os.environ.get('AUG_BATCH', '12'))    # 호출당 질문 수
NAMES = {0: '졸업요건', 1: '학교공지', 2: '학사일정', 3: '식단', 4: '통학셔틀'}


def main():
    key = os.environ.get('GEMINI_API_KEY', '').strip()
    if not key:
        print('[에러] GEMINI_API_KEY 없음'); sys.exit(1)
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=key)

    train = json.load(open(CLS / 'train.json', encoding='utf-8'))
    print(f'원본 train {len(train)}건, 질문당 {PER_Q} 패러프레이즈 목표', flush=True)

    aug = list(train)
    seen = {q['question'] for q in train}
    # 라벨별로 배치 처리(라벨 일관 프롬프트)
    by_label = {}
    for q in train:
        by_label.setdefault(q['label'], []).append(q['question'])

    for label, qs in by_label.items():
        for i in range(0, len(qs), BATCH):
            chunk = qs[i:i + BATCH]
            numbered = '\n'.join(f'{j+1}. {q}' for j, q in enumerate(chunk))
            prompt = (
                f'다음은 충남대 챗봇의 "{NAMES[label]}" 유형 질문들이다. '
                f'각 질문을 의미는 그대로 유지하되 어순/구어체/동의어를 바꿔 '
                f'{PER_Q}개씩 자연스러운 학생 말투로 패러프레이즈하라. '
                f'반드시 같은 유형({NAMES[label]})을 유지하라.\n'
                f'출력은 JSON 배열만: [{{"orig":1,"paraphrases":["..","..",".."]}}, ...]\n\n{numbered}')
            try:
                resp = client.models.generate_content(
                    model=MODEL, contents=prompt,
                    config=types.GenerateContentConfig(temperature=0.9))
                txt = (resp.text or '').strip()
                m = re.search(r'\[.*\]', txt, re.S)
                arr = json.loads(m.group(0)) if m else []
                for item in arr:
                    for p in item.get('paraphrases', []):
                        p = (p or '').strip()
                        if p and p not in seen and 4 <= len(p) <= 60:
                            seen.add(p)
                            aug.append({'question': p, 'label': label})
                print(f'  label {label} {NAMES[label]} [{i+len(chunk)}/{len(qs)}] 누적 {len(aug)}', flush=True)
            except Exception as e:
                print(f'  label {label} 배치 실패: {str(e)[:80]}', flush=True)
            time.sleep(0.5)

    json.dump(aug, open(CLS / 'train_aug.json', 'w', encoding='utf-8'),
              ensure_ascii=False, indent=2)
    import collections
    ctr = collections.Counter(s['label'] for s in aug)
    print(f'\n증강 완료: {len(train)} → {len(aug)} → data/cls/train_aug.json')
    for k in range(5):
        print(f'  label {k} {NAMES[k]}: {ctr[k]}')
    print('v2 학습: CLS_TRAIN=data/cls/train_aug.json 로 train_classifier.py 돌리면 됨'
          ' (스크립트가 train.json 고정이면 train_aug.json을 train.json으로 교체).')


if __name__ == '__main__':
    main()
