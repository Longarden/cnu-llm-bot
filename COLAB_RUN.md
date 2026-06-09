# Colab 실행 런북 (아침에 이대로)

마감용 산출물 생성 절차. 모든 코드 픽스는 main에 푸시됨(2026-06-02 밤 작업).

## A. 빠른 경로 — 드라이브에 chroma_db/model 백업해둔 경우

새 노트북, 런타임 T4. 셀 하나씩.

```python
# [셀 1] 코드 받기
!git clone https://github.com/Longarden/cnu-llm-bot.git
%cd cnu-llm-bot

# [셀 2] 의존성 (torch2.5.1 + torchvision0.20.1 + transformers<4.49 + ST3.4.1 + bitsandbytes)
!pip install -q -r requirements.txt

# [셀 3] 드라이브에서 인덱스/분류기 복원 (15분 빌드 스킵)
from google.colab import drive
drive.mount('/content/drive')
!cp -r /content/drive/MyDrive/cnu_chroma_db /content/cnu-llm-bot/chroma_db
!cp -r /content/drive/MyDrive/cnu_model     /content/cnu-llm-bot/model

# [셀 4] Task1 분류 산출물
!python src/classifier.py

# [셀 5] Task2 챗봇 산출물 (EXAONE-3.5-7.8B-Instruct + bitsandbytes 4bit, 첫 실행 시 모델 다운로드 ~2분)
!python src/gen_chat_output.py

# [셀 6] Task3 실시간 산출물
!python src/realtime_model.py
```

## B. 처음부터 (드라이브 백업 없을 때)

A의 셀3 대신:

```python
# 분류기 학습
!CLS_MODEL=klue/roberta-large CLS_MAX_LEN=128 CLS_EPOCHS=6 python scripts/train_classifier.py
# 인덱스 빌드 (bge-m3, 21707청크, ~15분)
!python scripts/rebuild_index.py
```

그다음 백업해두면 다음엔 빠른 경로로:

```python
!cp -r /content/cnu-llm-bot/chroma_db /content/drive/MyDrive/cnu_chroma_db
!cp -r /content/cnu-llm-bot/model     /content/drive/MyDrive/cnu_model
```

## 오늘 밤 바뀐 것 (왜 이전에 막혔나)

1. 생성모델: EXAONE-AWQ -> EXAONE-3.5-7.8B-Instruct(비-AWQ) + bitsandbytes 4bit(nf4).
   - autoawq가 transformers 4.51을 기대해 4.48에서 import로 죽던 문제 제거(AWQ 경로 회피).
   - 표준 모델 + bnb 4bit라 torch2.5.1/transformers4.48에서 안정. T4 ~5~6GB.
   - EXAONE은 한국어 네이티브라 중국어 코드스위칭이 없음. RopeParameters 이전 안전 리비전 자동 핀.
2. 식단/셔틀 거절 해소: chat_answer가 식단(3)/셔틀(4)은 realtime 라이브 크롤로 답함.
   - 정적 코퍼스가 얇아서(식단9·셔틀11건) 거절되던 구조. 라이브 우선 + 정적 폴백.
   - 끄려면 CHAT_REALTIME=0.
3. 거절 로직 보정: 청크는 있는데 절대점수가 없을 때 0점 강제거절 제거. DENSE 임계값 0.35->0.30.
4. test_chat.json 5 -> 16문항 (5유형 골고루).
5. 로컬 단위테스트 13개 통과(거절밴드/엣지케이스/라우팅). `py -3.13 tests/test_rejection_routing.py` 류.

## 확인 포인트

- 셀5 chat_output.json: "생성 오류"(AWQ/qwen3 import) 사라지고, 식단/셔틀이 "자료없음" 대신 라이브 답.
- 셀5 로그에 `[hybrid_retriever] dense 검색 실패` 없어야 함.
- 셀6 realtime_output.json: 식단/셔틀/공지 오늘자 라이브 데이터.

## 남은 일 (사람이 판단/제출)

- chat_output 16개 품질 검수 -> 약한 답 프롬프트/데이터 보강.
- 제출 패키징(zip), UI 시연 영상 2분, 발표 5분.
