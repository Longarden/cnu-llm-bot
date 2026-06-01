"""질문유형 분류기(Task1) 학습 — klue/bert-base + AutoModelForSequenceClassification.

과제 라벨: 졸업요건=0, 학교공지=1, 학사일정=2, 식단=3, 통학/셔틀=4 (num_labels=5).
입력: data/cls/train.json, data/cls/valid.json  (포맷 [{"question":"...","label":N}, ...])
평가: sklearn f1_score(macro) + accuracy.
저장: model/  (save_pretrained + tokenizer)  및  model/model.bin (state_dict).
환경: Python 3.10 / torch 2.5.1. GPU 있으면 GPU, 없으면 CPU 자동. 외부 API 없음(klue 모델은 HF에서 자동 다운로드).

실행(풀 학습, GPU 권장):
    python scripts/train_classifier.py

CPU 스모크(파이프라인 검증, 점수 무시):
    CLS_SMOKE=1 python scripts/train_classifier.py
    # 또는 개별 env: CLS_MAX_STEPS=40 CLS_EPOCHS=1

조정 가능한 env: CLS_MODEL, CLS_EPOCHS, CLS_MAX_LEN, CLS_LR, CLS_BATCH, CLS_MAX_STEPS, CLS_SMOKE.
"""
import os, sys, json
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import f1_score, accuracy_score
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    Trainer,
    TrainingArguments,
)
from torch.utils.data import Dataset

ROOT = Path(__file__).resolve().parent.parent
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

# ── 설정(env로 조정) ────────────────────────────────────────────────
MODEL_NAME = os.environ.get('CLS_MODEL', 'klue/bert-base')
NUM_LABELS = 5
MAX_LEN = int(os.environ.get('CLS_MAX_LEN', '64'))
LR = float(os.environ.get('CLS_LR', '2e-5'))
BATCH = int(os.environ.get('CLS_BATCH', '16'))
EPOCHS = float(os.environ.get('CLS_EPOCHS', '4'))
SMOKE = os.environ.get('CLS_SMOKE', '0') == '1'
# 스모크면 기본을 가볍게(개별 env가 우선)
MAX_STEPS = int(os.environ.get('CLS_MAX_STEPS', '40' if SMOKE else '-1'))
if SMOKE and 'CLS_EPOCHS' not in os.environ:
    EPOCHS = 1.0

DATA_DIR = ROOT / 'data' / 'cls'
TRAIN_PATH = DATA_DIR / 'train.json'
VALID_PATH = DATA_DIR / 'valid.json'
MODEL_DIR = ROOT / os.environ.get('CLS_OUT_DIR', 'model')  # arm별 폴더 분리(SOTA A/B)
MODEL_DIR.mkdir(parents=True, exist_ok=True)

LABEL_NAMES = ['졸업요건', '학교공지', '학사일정', '식단', '통학/셔틀']


def load_json(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


class ClsDataset(Dataset):
    def __init__(self, rows, tokenizer, max_len):
        self.enc = tokenizer(
            [r['question'] for r in rows],
            truncation=True, max_length=max_len, padding=False,
        )
        self.labels = [int(r['label']) for r in rows]

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, i):
        item = {k: torch.tensor(v[i]) for k, v in self.enc.items()}
        item['labels'] = torch.tensor(self.labels[i], dtype=torch.long)
        return item


def compute_metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    return {
        'f1_macro': f1_score(labels, preds, average='macro'),
        'accuracy': accuracy_score(labels, preds),
    }


def main():
    train_rows = load_json(TRAIN_PATH)
    valid_rows = load_json(VALID_PATH)
    print(f'[data] train={len(train_rows)}  valid={len(valid_rows)}  model={MODEL_NAME}')

    use_cuda = torch.cuda.is_available()
    use_fp16 = use_cuda  # GPU에서만 FP16, CPU는 FP32. 양자화 없음.
    print(f'[env] cuda={use_cuda}  fp16={use_fp16}  smoke={SMOKE}  max_steps={MAX_STEPS}  epochs={EPOCHS}')

    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_NAME, num_labels=NUM_LABELS,
    )

    train_ds = ClsDataset(train_rows, tokenizer, MAX_LEN)
    valid_ds = ClsDataset(valid_rows, tokenizer, MAX_LEN)

    # transformers 버전 차이를 흡수: eval/save 전략 인자명이 버전마다 다름.
    args_kwargs = dict(
        output_dir=str(ROOT / 'outputs' / 'cls_trainer'),
        per_device_train_batch_size=BATCH,
        per_device_eval_batch_size=BATCH,
        learning_rate=LR,
        num_train_epochs=EPOCHS,
        max_steps=MAX_STEPS,
        weight_decay=0.01,
        warmup_ratio=0.1,
        logging_steps=10,
        fp16=use_fp16,
        report_to=[],
        seed=42,
        save_total_limit=1,
    )
    try:
        training_args = TrainingArguments(
            eval_strategy='epoch', save_strategy='no', **args_kwargs,
        )
    except TypeError:
        # 구버전 transformers는 evaluation_strategy 사용
        training_args = TrainingArguments(
            evaluation_strategy='epoch', save_strategy='no', **args_kwargs,
        )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=valid_ds,
        tokenizer=tokenizer,
        compute_metrics=compute_metrics,
    )

    trainer.train()
    metrics = trainer.evaluate()
    f1 = metrics.get('eval_f1_macro')
    acc = metrics.get('eval_accuracy')
    print(f'[eval] f1_macro={f1:.4f}  accuracy={acc:.4f}')

    # ── 저장: save_pretrained(가중치+config) + tokenizer + model.bin(state_dict) ──
    try:
        model.save_pretrained(MODEL_DIR)
    except (ValueError, RuntimeError):
        # ELECTRA 등 비연속(non-contiguous) 텐서는 safetensors 저장 불가
        # → pytorch_model.bin(.bin)으로 저장. from_pretrained가 자동 로드함.
        model.save_pretrained(MODEL_DIR, safe_serialization=False)
    tokenizer.save_pretrained(MODEL_DIR)
    torch.save(model.state_dict(), MODEL_DIR / 'model.bin')
    # 추론용 라벨 메타(선택): 사람이 읽기 좋게 동봉.
    with open(MODEL_DIR / 'label_map.json', 'w', encoding='utf-8') as f:
        json.dump({str(i): n for i, n in enumerate(LABEL_NAMES)}, f, ensure_ascii=False, indent=2)

    print(f'[save] model dir = {MODEL_DIR}')
    print(f'[save] state_dict = {MODEL_DIR / "model.bin"}')
    print('[done] 풀 학습은 GPU에서 `python scripts/train_classifier.py` 로 실행.')


if __name__ == '__main__':
    main()
