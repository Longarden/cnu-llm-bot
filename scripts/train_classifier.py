"""질문유형 분류기(Task1) 학습 — CLI 진입점.

실제 학습 로직은 src/train_cls.py 에 있다. 노트북(src/classifier.ipynb)과 챗봇(chatbot.sh)이
같은 코드를 쓰도록 한 곳에 모아뒀고, 이 파일은 터미널에서 부르기 위한 얇은 래퍼다.

실행:
    python scripts/train_classifier.py            # 가중치 없으면 학습, 있으면 건너뜀
    python scripts/train_classifier.py --force    # 항상 새로 학습

조정 가능한 env: CLS_BASE_MODEL, CLS_EPOCHS, CLS_BATCH, CLS_LR, CLS_MAX_LEN, CLS_SEED
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.train_cls import train_classifier  # noqa: E402


def main():
    force = "--force" in sys.argv
    metrics = train_classifier(force=force)
    if metrics is None:
        print("이미 학습된 가중치가 있습니다. 다시 학습하려면 --force 를 붙이세요.")
        return 0
    print("\n[결과] valid   accuracy=%.4f  macro-F1=%.4f"
          % (metrics["valid"]["accuracy"], metrics["valid"]["f1_macro"]))
    if "natural" in metrics:
        print("[결과] 구어체  accuracy=%.4f  macro-F1=%.4f"
              % (metrics["natural"]["accuracy"], metrics["natural"]["f1_macro"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
