"""학습된 분류기(HF 모델 폴더)를 자연질문 held-out 평가셋으로 평가 → F1/acc/혼동.

SOTA A/B용. 같은 평가셋(data/cls/eval_natural.json, 템플릿과 다른 자연 말투)으로
여러 arm을 동일 기준 비교.

실행: python scripts/eval_classifiers.py <model_dir> [eval_json]
예:   python scripts/eval_classifiers.py model
      python scripts/eval_classifiers.py model_koelectra
"""
import sys, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

NAMES = {0: '졸업요건', 1: '공지', 2: '학사일정', 3: '식단', 4: '셔틀'}


def main():
    model_dir = sys.argv[1] if len(sys.argv) > 1 else 'model'
    eval_path = sys.argv[2] if len(sys.argv) > 2 else str(ROOT / 'data/cls/eval_natural.json')
    mdir = ROOT / model_dir if not Path(model_dir).is_absolute() else Path(model_dir)

    import torch
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    from sklearn.metrics import f1_score, accuracy_score, confusion_matrix

    rows = json.load(open(eval_path, encoding='utf-8'))
    tok = AutoTokenizer.from_pretrained(str(mdir))
    model = AutoModelForSequenceClassification.from_pretrained(str(mdir))
    model.eval()
    dev = 'cuda' if torch.cuda.is_available() else 'cpu'
    model.to(dev)

    y_true, y_pred, wrong = [], [], []
    for r in rows:
        enc = tok(r['question'], return_tensors='pt', truncation=True, max_length=128).to(dev)
        with torch.no_grad():
            pred = int(model(**enc).logits.argmax(-1).item())
        y_true.append(r['label'])
        y_pred.append(pred)
        if pred != r['label']:
            wrong.append((r['question'], r['label'], pred))

    f1 = f1_score(y_true, y_pred, average='macro')
    acc = accuracy_score(y_true, y_pred)
    per = f1_score(y_true, y_pred, average=None, labels=[0, 1, 2, 3, 4])
    print(f'\n=== {model_dir} on {Path(eval_path).name} (n={len(rows)}) ===')
    print(f'  f1_macro={f1:.4f}  accuracy={acc:.4f}')
    print('  라벨별 F1: ' + ' '.join(f'{NAMES[i]}={per[i]:.2f}' for i in range(5)))
    print(f'  오분류 {len(wrong)}건:')
    for q, t, p in wrong[:15]:
        print(f'    "{q}"  정답={NAMES[t]} 예측={NAMES[p]}')
    # 기계가독 결과(비교 집계용)
    out = {'model': model_dir, 'f1_macro': round(f1, 4), 'accuracy': round(acc, 4),
           'wrong': len(wrong), 'n': len(rows)}
    print('RESULT_JSON ' + json.dumps(out, ensure_ascii=False))


if __name__ == '__main__':
    main()
