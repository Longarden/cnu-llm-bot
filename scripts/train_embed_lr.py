"""대조군: bge-m3 임베딩 + LogisticRegression 분류기 (소량데이터 강건, GPU학습 0).

train.json 질문을 bge-m3로 임베딩 → LogReg 학습 → eval_natural.json으로 평가.
SOTA A/B의 대조군 arm. 캐시된 bge-m3로 CPU에서 수분이면 됨.

실행: python scripts/train_embed_lr.py
"""
import sys, json, pickle
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

CLS = ROOT / 'data' / 'cls'
NAMES = {0: '졸업요건', 1: '공지', 2: '학사일정', 3: '식단', 4: '셔틀'}
EMB_MODEL = 'BAAI/bge-m3'


def main():
    from sentence_transformers import SentenceTransformer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import f1_score, accuracy_score

    train = json.load(open(CLS / 'train.json', encoding='utf-8'))
    ev = json.load(open(CLS / 'eval_natural.json', encoding='utf-8'))
    print(f'train {len(train)} / eval_natural {len(ev)} | 임베딩 {EMB_MODEL}', flush=True)

    enc = SentenceTransformer(EMB_MODEL)  # 캐시 사용, CPU 가능
    Xtr = enc.encode([r['question'] for r in train], normalize_embeddings=True,
                     show_progress_bar=True)
    ytr = [r['label'] for r in train]
    Xev = enc.encode([r['question'] for r in ev], normalize_embeddings=True)
    yev = [r['label'] for r in ev]

    clf = LogisticRegression(max_iter=2000, C=10.0, class_weight='balanced')
    clf.fit(Xtr, ytr)
    pred = clf.predict(Xev)

    f1 = f1_score(yev, pred, average='macro')
    acc = accuracy_score(yev, pred)
    per = f1_score(yev, pred, average=None, labels=[0, 1, 2, 3, 4])
    print(f'\n=== embed(bge-m3)+LogReg on eval_natural (n={len(ev)}) ===')
    print(f'  f1_macro={f1:.4f}  accuracy={acc:.4f}')
    print('  라벨별 F1: ' + ' '.join(f'{NAMES[i]}={per[i]:.2f}' for i in range(5)))
    wrong = [(ev[i]['question'], yev[i], int(pred[i])) for i in range(len(ev)) if pred[i] != yev[i]]
    print(f'  오분류 {len(wrong)}건:')
    for q, t, p in wrong[:15]:
        print(f'    "{q}"  정답={NAMES[t]} 예측={NAMES[p]}')

    (ROOT / 'model_embedlr').mkdir(exist_ok=True)
    pickle.dump(clf, open(ROOT / 'model_embedlr' / 'logreg.pkl', 'wb'))
    out = {'model': 'embed(bge-m3)+LogReg', 'f1_macro': round(f1, 4),
           'accuracy': round(acc, 4), 'wrong': len(wrong), 'n': len(ev)}
    print('RESULT_JSON ' + json.dumps(out, ensure_ascii=False))


if __name__ == '__main__':
    main()
