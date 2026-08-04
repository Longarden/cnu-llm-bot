# CNU Campus ChatBot — 충남대학교 캠퍼스 챗봇

질문유형 분류기 + 소프트 라우팅 RAG + 로컬 생성으로 충남대 학내정보(졸업요건·공지·학사일정·식단·셔틀)를 안내하는 완전 로컬 챗봇입니다. 외부 API 없이 동작합니다.

## 평가 시 실행 대상

채점자는 다음 두 가지만 실행합니다 (과제 사양 PDF p20).

1. `src/classifier.ipynb` — 질문유형 분류기(Task1). 데이터 생성 → 학습 → 평가 → `outputs/cls_output.json` 생성
2. `chatbot.sh` — 챗봇(Task2). `data/test_chat.json` → `outputs/chat_output.json` 생성 후 Gradio UI 실행

**clone 직후 바로 실행할 수 있습니다.** 용량 때문에 깃에서 빠진 두 자산은 실행 시 자동으로 만들어집니다.

| 빠진 자산 | 없을 때 동작 | 소요 |
|---|---|---|
| `model/` 분류기 가중치 | `data/cls/` 로 klue/roberta-base 파인튜닝 후 저장 | GPU 수 분 |
| `chroma_db/` 벡터DB | 커밋된 `data/crawled/` 로 인덱스 재생성 | 수 분 |

두 자산 모두 한 번 만들어지면 이후 실행에서는 재사용합니다.

## 질문유형 5카테고리

| label | 유형 | RAG 검색 카테고리 |
|-------|------|-------------------|
| 0 | 졸업요건 | B_academic, F_department, department_general |
| 1 | 학교공지 | K_notices, F_department |
| 2 | 학사일정 | B_academic |
| 3 | 식단 | A_dining |
| 4 | 통학/셔틀 | A_shuttle |

졸업요건/공지는 학과별 정보라 학과 카테고리도 포함합니다.

## 동작 구조

```
질문
  → 질문유형 분류기 (model/, klue/roberta-base 파인튜닝, label 0~4, CPU 추론 가능)
  → 분류 결과로 data_category 소프트 라우팅
  → 하이브리드 RAG 검색 (BM25 sparse + dense + Reciprocal Rank Fusion → reranker)
  → 로컬 생성 (EXAONE-3.5-7.8B-Instruct + bitsandbytes 4bit, GEN_BACKEND=local)
  → 답변
```

## 디렉터리

```
src/          classifier.ipynb(채점 진입점) · train_cls.py(학습) · chat_pipeline.py(코어)
              gen_chat_output.py · realtime_model.py · chatbot_ui.py · run_all.py
data/         cls/(분류기 학습셋) · crawled/(크롤링 원본) · test_*.json(평가 입력)
model/        분류기 토크나이저/설정. 가중치는 실행 시 학습되어 여기 저장됨
retrieval/    하이브리드 검색 · 리랭커 · 카테고리 라우팅 · 날짜 추출
embedding/    bge-m3 임베더 · Chroma 벡터스토어 · 청커 · 데이터 로더
generation/   프롬프트 · EXAONE 로컬 생성 · CRAG 거절 게이트
crawlers/     사이트별 크롤러 15종
crawler_pipeline/  본문 추출 · 텍스트 보정 · 중복 제거 · 요약
interface/    RAG 답변 조립
scripts/      학습/인덱스 빌드/검증/패키징 스크립트
notebooks/    콜랩 실행·검증 노트북
docs/         콜랩 실행 가이드 · 평가 기록
tests/        파이프라인 점검 스크립트
```

## 핵심 소스 (`src/`)

- `classifier.ipynb` — **채점 진입점.** 데이터 생성 → 학습 → 평가 → 예측을 한 번에 실행
- `train_cls.py` — 분류기 학습 모듈. 노트북과 `chatbot.sh` 가 공유한다
- `classifier.py` — 노트북과 같은 일을 하는 CLI (`python src/classifier.py`)
- `chat_pipeline.py` — 챗봇 코어(분류 → 라우팅 → RAG → 생성)
- `gen_chat_output.py` — 배치 추론, `test_chat.json` → `chat_output.json`
- `chatbot_ui.py` — Gradio ChatInterface UI
- `realtime_model.py` — (옵션 Task3) 라이브 크롤 후 최신 답변

## 환경 / 설치

- Python 3.10, torch 2.5.1. GPU 있으면 GPU, 없으면 CPU 자동 (분류기는 CPU로도 충분)

```bash
pip install -r requirements.txt
# CUDA 빌드는 별도 인덱스 권장
pip install torch==2.5.1 --index-url https://download.pytorch.org/whl/cu121
```

## 실행

```bash
# (1) 분류기 — 노트북(src/classifier.ipynb) 실행, 또는 CLI로
python src/classifier.py            # 가중치 없으면 학습 후 예측
python src/classifier.py --force    # 항상 새로 학습

# (2) 챗봇 — 배치 추론 + Gradio UI
bash chatbot.sh                     # data/test_chat.json → outputs/chat_output.json + UI
```

CPU에서 생성모델이 무거우면 스텁 모드로 포맷/흐름만 검증할 수 있습니다.

```bash
CHAT_STUB=1 python src/gen_chat_output.py
REALTIME_STUB=1 python src/realtime_model.py
```

## 분류기 학습

학습 데이터는 `scripts/build_cls_dataset.py` 가 템플릿 x 슬롯 조합으로 생성합니다 (라벨당 600개, train 2700 / valid 300, 문자열 중복 0). 사람이 직접 쓴 구어체 평가셋 `data/cls/eval_natural.json` 50문항은 생성 대상이 아니며, 템플릿 밖 일반화 성능을 재는 데 씁니다.

```bash
python scripts/build_cls_dataset.py     # 학습셋 재생성 (seed 고정, 결과 재현됨)
python scripts/train_classifier.py      # 학습 (--force 로 재학습)
```

조정 가능한 환경변수: `CLS_BASE_MODEL`, `CLS_EPOCHS`, `CLS_BATCH`, `CLS_LR`, `CLS_MAX_LEN`, `CLS_SEED`

## 평가용 테스트셋 교체법

`data/` 의 아래 파일을 채점용 파일로 교체하면 됩니다 (포맷 동일).

- `data/test_cls.json` — `[{"question": "..."}, ...]`
- `data/test_chat.json` — `[{"user": "..."}, ...]`
- (옵션) `data/test_realtime.json` — `[{"user": "..."}, ...]`

해당 파일이 없으면 `data/cls/valid.json` 에서 임시 스모크셋을 생성합니다.

## outputs 산출물

| 파일 | 생성 주체 | 포맷 |
|------|-----------|------|
| `outputs/cls_output.json` | classifier (Task1) | `[{"id":N,"question":"...","label":N}, ...]` (label 0~4) |
| `outputs/chat_output.json` | chatbot.sh (Task2) | `[{"id":N,"user":"...","model":"..."}, ...]` |
| `outputs/realtime_output.json` | realtime (Task3, 옵션) | `[{"id":N,"user":"...","model":"..."}, ...]` |

`id` 는 입력행에 `id` 가 있으면 그 값을, 없으면 0부터의 인덱스를 사용합니다.

## 검증 / 패키징

```bash
bash scripts/verify.sh              # 구조·양식만 (빠름)
bash scripts/verify.sh stub         # EXAONE 없이 파이프라인까지
bash scripts/verify.sh full         # 학습 + 실제 출력 생성까지

TEAM=조이름 NAME=홍길동 bash scripts/package_submission.sh
INCLUDE_MODEL=1 TEAM=조이름 NAME=홍길동 bash scripts/package_submission.sh   # 가중치 동봉
```

`dist/Termproject_<NAME>/` 와 동명 zip 이 생성됩니다. 가중치를 동봉하지 않아도 채점 환경에서 자동 학습되므로 그대로 제출할 수 있습니다.
