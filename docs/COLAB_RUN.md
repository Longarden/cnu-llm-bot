# Colab 실행 런북

T4 런타임 기준. clone 직후 그대로 실행할 수 있습니다 — 분류기 가중치와 벡터DB가 없으면
각 진입점이 감지해서 스스로 만듭니다.

## 기본 경로 (처음부터)

```python
# [셀 1] 코드 받기
!git clone https://github.com/Longarden/CNU-Campus-ChatBot-.git
%cd CNU-Campus-ChatBot-

# [셀 2] 의존성 (torch 2.5.1 + torchvision 0.20.1 + transformers<4.49 + ST 3.4.1 + bitsandbytes)
!pip install -q -r requirements.txt

# [셀 3] Task1 분류기 — 데이터 생성 → 학습 → 평가 → 예측
#        노트북으로 하려면 src/classifier.ipynb 를 위에서부터 실행해도 결과가 같다.
!python src/classifier.py            # → outputs/cls_output.json

# [셀 4] Task2 챗봇 — 첫 실행에서 chroma 인덱스 빌드(~15분) + EXAONE 다운로드(~2분)
!python src/gen_chat_output.py       # → outputs/chat_output.json

# [셀 5] Task3 실시간 (옵션)
!python src/realtime_model.py        # → outputs/realtime_output.json
```

`chatbot.sh` 는 위 배치 3개와 Gradio UI 를 단일 프로세스로 묶어 실행합니다 (생성모델 1회 로드).

```python
!bash chatbot.sh
```

Colab 에서 UI 를 열 때는 좌측 **포트(Ports)** 탭에서 7860 을 여세요.
cloudflared 퀵터널은 origin 100초 한도가 있어 느린 라이브 답변에서 524 가 납니다.
외부 공개 URL 이 필요하면 `GRADIO_SHARE=1`.

## 빌드 산출물 재사용 (두 번째 실행부터)

인덱스 빌드와 분류기 학습은 한 번만 하면 됩니다. 드라이브에 백업해두면 다음 세션에서 건너뜁니다.

```python
from google.colab import drive
drive.mount('/content/drive')

# 백업
!cp -r chroma_db /content/drive/MyDrive/cnu_chroma_db
!cp -r model     /content/drive/MyDrive/cnu_model

# 복원 (셀 3 이전에)
!cp -r /content/drive/MyDrive/cnu_chroma_db ./chroma_db
!cp -r /content/drive/MyDrive/cnu_model     ./model
```

## 분류기 하이퍼파라미터 조정

```python
!CLS_BASE_MODEL=klue/roberta-large CLS_MAX_LEN=128 CLS_EPOCHS=6 python scripts/train_classifier.py --force
```

조정 가능: `CLS_BASE_MODEL`, `CLS_EPOCHS`, `CLS_BATCH`, `CLS_LR`, `CLS_MAX_LEN`, `CLS_SEED`
학습셋 크기는 `CLS_PER_LABEL=800 python scripts/build_cls_dataset.py` 로 바꿉니다.

## 확인 포인트

- `outputs/cls_output.json` — `label` 이 0~4 정수인지, 건수가 입력과 같은지
- `outputs/chat_output.json` — "생성 오류" 문자열이 없고, 식단/셔틀이 "자료 없음" 대신 라이브 답변인지
- 로그에 `[hybrid_retriever] dense 검색 실패` 가 없어야 함
- 인덱스가 비어 있으면 `[vector_store] chroma_db 인덱스가 비어 있습니다` 로그 뒤 재생성이 돌아감

## 스텁 모드 (EXAONE 없이 흐름만 검증)

```bash
CHAT_STUB=1 python src/gen_chat_output.py
REALTIME_STUB=1 python src/realtime_model.py
bash scripts/verify.sh stub
```
