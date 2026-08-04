"""질문유형 분류기(Task1) CLI — src/classifier.ipynb 과 같은 일을 터미널에서 한다.

흐름: 학습 데이터 확인 → (가중치 없으면) 학습 → data/test_cls.json 예측 → outputs/cls_output.json

입력 : data/test_cls.json      (포맷 [{"question": "..."}, ...])
출력 : outputs/cls_output.json (포맷 [{"id": N, "question": "...", "label": 0~4}, ...])

학습 로직은 src/train_cls.py 에 있다. 노트북과 이 CLI 가 같은 코드를 쓰므로 결과가 갈리지 않는다.
test_cls.json 이 없으면 data/cls/valid.json 의 question 만 떼서 임시 생성한다(스모크).

실행:
    python src/classifier.py
    python src/classifier.py --force    # 분류기를 새로 학습한 뒤 예측
"""
import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from src.train_cls import (  # noqa: E402
    LABEL_NAMES, load_rows, predict_labels, train_classifier,
)

CLS_DIR = ROOT / "data" / "cls"
TEST_PATH = ROOT / "data" / "test_cls.json"
OUT_PATH = ROOT / "outputs" / "cls_output.json"


def main():
    force = "--force" in sys.argv

    # 1) 가중치가 없으면 학습해서 만든다(force 면 항상 새로 학습).
    train_classifier(force=force)

    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    device = "cuda" if torch.cuda.is_available() else "cpu"
    tokenizer = AutoTokenizer.from_pretrained(str(ROOT / "model"))
    model = AutoModelForSequenceClassification.from_pretrained(str(ROOT / "model"))
    model.to(device).eval()

    # 2) 테스트 입력 확보
    if not TEST_PATH.exists():
        TEST_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(TEST_PATH, "w", encoding="utf-8") as f:
            json.dump([{"question": r["question"]} for r in load_rows(CLS_DIR / "valid.json")],
                      f, ensure_ascii=False, indent=2)
        print("test_cls.json 이 없어 valid 로 임시 생성했습니다:", TEST_PATH)

    test_rows = load_rows(TEST_PATH)
    questions = [r["question"] for r in test_rows]

    # 3) 예측 → 제출 양식으로 저장
    preds = predict_labels(model, tokenizer, questions, device)
    out = [{"id": test_rows[i].get("id", i), "question": q, "label": int(p)}
           for i, (q, p) in enumerate(zip(questions, preds))]
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print("%d건 예측 → %s" % (len(out), OUT_PATH))
    print("예측 분포:", {LABEL_NAMES[k]: v for k, v in sorted(collections.Counter(preds).items())})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
