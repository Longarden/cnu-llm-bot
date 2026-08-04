"""질문유형 분류기(Task1) 학습 — src/classifier.ipynb 와 chatbot.sh 가 공유하는 학습 모듈.

왜 별도 모듈인가
    분류기 가중치(model/*.safetensors)는 용량 때문에 .gitignore 로 제외된다.
    즉 clone 직후에는 model/ 에 토크나이저와 config 만 있고 가중치가 없다.
    그 상태로 classifier.ipynb 나 chatbot.sh 를 돌리면 from_pretrained 가 실패한다.
    그래서 "가중치가 없으면 그 자리에서 학습해서 만든다"를 두 진입점이 공유하도록 여기 모았다.

학습 방식
    klue/roberta-base + AutoModelForSequenceClassification(num_labels=5) 파인튜닝.
    transformers 의 Trainer 대신 순수 PyTorch 루프를 쓴다. Trainer 는 버전마다 인자명이
    바뀌고(evaluation_strategy → eval_strategy, tokenizer → processing_class) accelerate 까지
    끌어들여서, 채점 환경이 조금만 달라도 깨진다. 데이터가 3천 건 규모라 루프가 더 단순하고 빠르다.

사용
    from src.train_cls import ensure_classifier, train_classifier
    ensure_classifier()            # 가중치 없으면 학습, 있으면 그대로 둠
    train_classifier(force=True)   # 항상 새로 학습

환경변수: CLS_BASE_MODEL, CLS_EPOCHS, CLS_BATCH, CLS_LR, CLS_MAX_LEN, CLS_SEED
"""
import json
import os
import random
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader, Dataset

ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = ROOT / "model"
DATA_DIR = ROOT / "data" / "cls"
TRAIN_PATH = DATA_DIR / "train.json"
VALID_PATH = DATA_DIR / "valid.json"
NATURAL_PATH = DATA_DIR / "eval_natural.json"

LABEL_NAMES = ["졸업요건", "학교공지", "학사일정", "식단", "통학/셔틀"]
NUM_LABELS = len(LABEL_NAMES)

BASE_MODEL = os.environ.get("CLS_BASE_MODEL", "klue/roberta-base")
EPOCHS = int(os.environ.get("CLS_EPOCHS", "3"))
BATCH = int(os.environ.get("CLS_BATCH", "32"))
LR = float(os.environ.get("CLS_LR", "3e-5"))
MAX_LEN = int(os.environ.get("CLS_MAX_LEN", "64"))
SEED = int(os.environ.get("CLS_SEED", "42"))

# from_pretrained 가 인식하는 가중치 파일명. 하나라도 있으면 학습된 모델로 본다.
WEIGHT_FILES = ("model.safetensors", "pytorch_model.bin")


def set_seed(seed=SEED):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def has_trained_weights(model_dir=MODEL_DIR):
    """model/ 에 실제 학습 가중치가 있는지. 토크나이저/config 만 있으면 False."""
    return any((Path(model_dir) / name).exists() for name in WEIGHT_FILES)


def load_rows(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def ensure_dataset():
    """학습 데이터가 없으면 scripts/build_cls_dataset.py 로 생성한다."""
    if TRAIN_PATH.exists() and VALID_PATH.exists():
        return
    import subprocess
    import sys
    builder = ROOT / "scripts" / "build_cls_dataset.py"
    print("[train_cls] 학습 데이터 없음 → %s 실행" % builder.name)
    subprocess.run([sys.executable, str(builder)], check=True, cwd=str(ROOT))


class QuestionDataset(Dataset):
    def __init__(self, rows, tokenizer, max_len=MAX_LEN):
        self.enc = tokenizer(
            [r["question"] for r in rows],
            truncation=True, max_length=max_len, padding="max_length",
            return_tensors="pt",
        )
        self.labels = torch.tensor([int(r["label"]) for r in rows], dtype=torch.long)

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, i):
        item = {k: v[i] for k, v in self.enc.items()}
        item["labels"] = self.labels[i]
        return item


@torch.no_grad()
def predict_labels(model, tokenizer, questions, device, batch=64, max_len=MAX_LEN):
    """질문 리스트 → 예측 라벨 리스트."""
    model.eval()
    preds = []
    for i in range(0, len(questions), batch):
        enc = tokenizer(
            questions[i:i + batch], truncation=True, max_length=max_len,
            padding=True, return_tensors="pt",
        ).to(device)
        preds.extend(model(**enc).logits.argmax(dim=-1).cpu().tolist())
    return preds


def score(gold, pred):
    """accuracy 와 macro-F1 을 sklearn 없이 계산한다(의존성 최소화)."""
    n = len(gold)
    acc = sum(int(g == p) for g, p in zip(gold, pred)) / n if n else 0.0
    f1s = []
    for label in range(NUM_LABELS):
        tp = sum(1 for g, p in zip(gold, pred) if g == label and p == label)
        fp = sum(1 for g, p in zip(gold, pred) if g != label and p == label)
        fn = sum(1 for g, p in zip(gold, pred) if g == label and p != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1s.append(2 * precision * recall / (precision + recall) if precision + recall else 0.0)
    return {"accuracy": acc, "f1_macro": sum(f1s) / NUM_LABELS, "f1_per_label": f1s}


def confusion(gold, pred):
    """행=정답, 열=예측 인 5x5 혼동행렬."""
    matrix = [[0] * NUM_LABELS for _ in range(NUM_LABELS)]
    for g, p in zip(gold, pred):
        matrix[g][p] += 1
    return matrix


def train_classifier(force=False, epochs=EPOCHS, verbose=True):
    """분류기를 학습해 model/ 에 저장하고 평가 지표를 돌려준다.

    force=False 이고 이미 가중치가 있으면 학습을 건너뛴다.
    """
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    if not force and has_trained_weights():
        if verbose:
            print("[train_cls] 이미 학습된 가중치가 있어 학습을 건너뜁니다: %s" % MODEL_DIR)
        return None

    ensure_dataset()
    set_seed()

    train_rows = load_rows(TRAIN_PATH)
    valid_rows = load_rows(VALID_PATH)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    if verbose:
        print("[train_cls] base=%s  train=%d  valid=%d  device=%s  epochs=%d"
              % (BASE_MODEL, len(train_rows), len(valid_rows), device, epochs))

    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    model = AutoModelForSequenceClassification.from_pretrained(
        BASE_MODEL,
        num_labels=NUM_LABELS,
        id2label={i: name for i, name in enumerate(LABEL_NAMES)},
        label2id={name: i for i, name in enumerate(LABEL_NAMES)},
    ).to(device)

    loader = DataLoader(
        QuestionDataset(train_rows, tokenizer), batch_size=BATCH, shuffle=True,
        generator=torch.Generator().manual_seed(SEED),
    )
    optimizer = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=0.01)
    total_steps = len(loader) * epochs
    scheduler = torch.optim.lr_scheduler.OneCycleLR(
        optimizer, max_lr=LR, total_steps=total_steps, pct_start=0.1, anneal_strategy="linear",
    )

    for epoch in range(1, epochs + 1):
        model.train()
        running = 0.0
        for step, batch in enumerate(loader, 1):
            batch = {k: v.to(device) for k, v in batch.items()}
            loss = model(**batch).loss
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()
            optimizer.zero_grad()
            running += loss.item()
        valid_metrics = score(
            [int(r["label"]) for r in valid_rows],
            predict_labels(model, tokenizer, [r["question"] for r in valid_rows], device),
        )
        if verbose:
            print("[train_cls] epoch %d/%d  loss=%.4f  valid_acc=%.4f  valid_f1=%.4f"
                  % (epoch, epochs, running / len(loader),
                     valid_metrics["accuracy"], valid_metrics["f1_macro"]))

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(MODEL_DIR)
    tokenizer.save_pretrained(MODEL_DIR)
    with open(MODEL_DIR / "label_map.json", "w", encoding="utf-8") as f:
        json.dump({str(i): n for i, n in enumerate(LABEL_NAMES)}, f, ensure_ascii=False, indent=2)
    if verbose:
        print("[train_cls] 저장 완료 → %s" % MODEL_DIR)

    results = {"valid": valid_metrics}
    # 템플릿 밖 구어체 평가셋으로 일반화 성능도 같이 본다(있을 때만).
    if NATURAL_PATH.exists():
        natural_rows = load_rows(NATURAL_PATH)
        natural_pred = predict_labels(
            model, tokenizer, [r["question"] for r in natural_rows], device)
        results["natural"] = score([int(r["label"]) for r in natural_rows], natural_pred)
        results["natural_confusion"] = confusion(
            [int(r["label"]) for r in natural_rows], natural_pred)
        if verbose:
            print("[train_cls] eval_natural(사람이 쓴 구어체 %d건)  acc=%.4f  f1=%.4f"
                  % (len(natural_rows), results["natural"]["accuracy"],
                     results["natural"]["f1_macro"]))
    return results


def ensure_classifier(verbose=True):
    """가중치가 없으면 학습해서 만든다. chatbot.sh / classifier.ipynb 공용 진입점."""
    if has_trained_weights():
        return False
    if verbose:
        print("[train_cls] model/ 에 학습 가중치가 없습니다 → 지금 학습합니다.")
    train_classifier(force=True, verbose=verbose)
    return True


if __name__ == "__main__":
    train_classifier(force=os.environ.get("CLS_FORCE", "0") == "1")
