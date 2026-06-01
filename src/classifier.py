"""질문유형 분류기(Task1) 추론 — model/ 로드 → data/test_cls.json 예측 → outputs/cls_output.json.

입력 : data/test_cls.json   (포맷 [{"question":"..."}, ...])
출력 : outputs/cls_output.json (포맷 [{"question":"...","label":N}, ...], label은 0~4 정수)
모델 : model/  (scripts/train_classifier.py 로 학습한 분류기)

test_cls.json 이 없으면 data/cls/valid.json 의 question 만 떼서 임시 생성(스모크).
환경: Python 3.10 / torch 2.5.1. GPU 있으면 GPU, 없으면 CPU 자동.

실행: python src/classifier.py
"""
import sys, json
from pathlib import Path

import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

# 노트북(.ipynb)에서는 __file__ 이 없으므로 cwd 기반으로도 ROOT 를 잡는다.
try:
    ROOT = Path(__file__).resolve().parent.parent
except NameError:
    ROOT = Path.cwd()
    if (ROOT / 'src').exists() is False and (ROOT.parent / 'model').exists():
        ROOT = ROOT.parent
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

MODEL_DIR = ROOT / 'model'
TEST_PATH = ROOT / 'data' / 'test_cls.json'
OUT_DIR = ROOT / 'outputs'
OUT_PATH = OUT_DIR / 'cls_output.json'
VALID_PATH = ROOT / 'data' / 'cls' / 'valid.json'
MAX_LEN = 64
BATCH = 32


def ensure_test_file():
    """test_cls.json 이 없으면 valid.json 의 question 만 떼서 임시 생성."""
    if TEST_PATH.exists():
        return
    if not VALID_PATH.exists():
        raise FileNotFoundError(f'{TEST_PATH} 도 {VALID_PATH} 도 없습니다.')
    with open(VALID_PATH, encoding='utf-8') as f:
        rows = json.load(f)
    test_rows = [{'question': r['question']} for r in rows]
    TEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(TEST_PATH, 'w', encoding='utf-8') as f:
        json.dump(test_rows, f, ensure_ascii=False, indent=2)
    print(f'[init] test_cls.json 이 없어 valid 에서 임시 생성: {TEST_PATH} (n={len(test_rows)})')


def main():
    ensure_test_file()

    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f'[env] device={device}  model_dir={MODEL_DIR}')

    tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_DIR)
    model.to(device)
    model.eval()

    with open(TEST_PATH, encoding='utf-8') as f:
        test_rows = json.load(f)
    questions = [r['question'] for r in test_rows]

    preds = []
    with torch.no_grad():
        for i in range(0, len(questions), BATCH):
            batch = questions[i:i + BATCH]
            enc = tokenizer(
                batch, truncation=True, max_length=MAX_LEN,
                padding=True, return_tensors='pt',
            ).to(device)
            logits = model(**enc).logits
            preds.extend(logits.argmax(dim=-1).cpu().tolist())

    out = [{'question': q, 'label': int(p)} for q, p in zip(questions, preds)]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f'[done] {len(out)}건 예측 → {OUT_PATH}')
    for row in out[:3]:
        print('   ', json.dumps(row, ensure_ascii=False))


if __name__ == '__main__':
    main()
