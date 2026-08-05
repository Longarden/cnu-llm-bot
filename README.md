# CNU Campus ChatBot — 충남대학교 캠퍼스 챗봇

질문유형 분류기 + 소프트 라우팅 RAG + 로컬 생성으로 충남대 학내정보(졸업요건·공지·학사일정·식단·셔틀)를 안내하는 완전 로컬 챗봇입니다. 외부 API 없이 동작합니다.

## 평가 시 실행 대상 (중요)

채점자는 다음 두 가지만 실행합니다 (과제 사양 PDF p20).

1. `src/classifier.ipynb` — 질문유형 분류기(Task1). `data/test_cls.json` 을 읽어 `outputs/cls_output.json` 생성.
2. `chatbot.sh` — 챗봇(Task2). `data/test_chat.json` 을 읽어 `outputs/chat_output.json` 생성 후 Gradio UI 실행.

`outputs/` 의 산출물은 평가 과정에서 자동 생성됩니다. 제출 zip 안의 `outputs/` 는 비어 있어도 됩니다.

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
  → 질문유형 분류기 (model/, klue/roberta-base 기반, label 0~4, CPU 추론 가능)
  → 분류 결과로 data_category 소프트 라우팅
  → 하이브리드 RAG 검색 (BM25 sparse + dense + Reciprocal Rank Fusion → reranker)
  → 로컬 생성 (EXAONE-3.5-7.8B-Instruct + bitsandbytes 4bit, generation/llm.py, GEN_BACKEND=local)
  → 답변
```

## 디렉터리

```
src/          classifier.ipynb(채점 진입점) · classifier.py · chat_pipeline.py(코어)
              gen_chat_output.py · realtime_model.py · chatbot_ui.py · run_all.py
data/         cls/(분류기 학습셋) · crawled/(크롤링 원본) · test_*.json(평가 입력)
model/        분류기 가중치와 토크나이저 (가중치는 드라이브 복원, 아래 참고)
retrieval/    하이브리드 검색 · 리랭커 · 카테고리 라우팅 · 날짜 추출
embedding/    bge-m3 임베더 · Chroma 벡터스토어 · 청커 · 데이터 로더
generation/   프롬프트 · EXAONE 로컬 생성 · CRAG 거절 게이트
crawlers/     사이트별 크롤러 15종
crawler_pipeline/  본문 추출 · 텍스트 보정 · 중복 제거 · 요약
interface/    RAG 답변 조립
scripts/      학습 · 인덱스 빌드 · 평가 · 검증 · 패키징 스크립트
notebooks/    콜랩 실행 노트북
docs/         콜랩 실행 런북 · 평가 기록
tests/        단위 테스트
eval/         평가 · LLM judge · 테스트셋 빌더
```

핵심 소스(`src/`):
- `classifier.ipynb` / `classifier.py` — 분류기 추론, `test_cls.json` → `cls_output.json`
- `chat_pipeline.py` — 챗봇 코어(분류 → 라우팅 → RAG → 생성)
- `gen_chat_output.py` — 배치 추론, `test_chat.json` → `chat_output.json`
- `chatbot_ui.py` — Gradio ChatInterface UI
- `realtime_model.py` — (옵션 Task3) 셔틀/식단/공지 라이브 크롤 후 최신 답변, `test_realtime.json` → `realtime_output.json`

## 환경

- Python 3.10
- torch 2.5.1
- GPU 있으면 GPU, 없으면 CPU 자동 (분류기는 CPU로도 충분)

## 설치

```bash
pip install -r requirements.txt
```

torch 는 CUDA 빌드를 별도 인덱스에서 설치하는 것을 권장합니다.

```bash
pip install torch==2.5.1 --index-url https://download.pytorch.org/whl/cu121
```

## 실행

```bash
# (1) 분류기 — 노트북 실행 또는
python src/classifier.py            # data/test_cls.json → outputs/cls_output.json

# (2) 챗봇 — 배치 추론 + Gradio UI
bash chatbot.sh                     # data/test_chat.json → outputs/chat_output.json + UI

# (옵션) Task3 실시간 반영
REALTIME=1 bash chatbot.sh          # data/test_realtime.json → outputs/realtime_output.json
```

CPU에서 로컬 생성모델이 무거우면 스텁 모드로 포맷/흐름만 검증할 수 있습니다.

```bash
CHAT_STUB=1 python src/gen_chat_output.py
REALTIME_STUB=1 python src/realtime_model.py
```

## 평가용 테스트셋 교체법

`data/` 의 아래 파일을 채점용 파일로 교체하면 됩니다 (포맷 동일).

- `data/test_cls.json` — `[{"question": "..."}, ...]`
- `data/test_chat.json` — `[{"user": "..."}, ...]`
- (옵션) `data/test_realtime.json` — `[{"user": "..."}, ...]`

해당 파일이 없으면 스크립트가 `data/cls/valid.json` 에서 임시 스모크셋을 생성합니다.

## outputs 산출물

| 파일 | 생성 주체 | 포맷 |
|------|-----------|------|
| `outputs/cls_output.json` | classifier (Task1) | `[{"id":N,"question":"...","label":N}, ...]` (label 0~4) |
| `outputs/chat_output.json` | chatbot.sh (Task2) | `[{"id":N,"user":"...","model":"..."}, ...]` |
| `outputs/realtime_output.json` | realtime (Task3, 옵션) | `[{"id":N,"user":"...","model":"..."}, ...]` |

`id` 는 입력행에 `id` 가 있으면 그 값을, 없으면 0부터의 인덱스를 사용합니다(공식 더미 양식과 동일).

## 용량 큰 자산(model/ · chroma_db/) — 구글드라이브 링크로 복원

분류기 가중치 `model/` 과 벡터DB `chroma_db/` 는 용량이 커서 제출 zip 에 넣지 않고 구글드라이브로 배포합니다.

1. `model.tar.gz`, `chroma_db.tar.gz` 를 구글드라이브에 올리고 "링크가 있는 모든 사용자: 뷰어"로 공유.
2. `restore_assets.sh` 의 `MODEL_ID` / `CHROMA_ID` 를 각 파일ID로 교체.
3. 콜랩에서 복원:

```bash
bash restore_assets.sh        # 드라이브에서 model/ + chroma_db/ 받아 압축해제
```

그 뒤 `src/classifier.ipynb` 와 `chatbot.sh` 를 실행하면 됩니다. (model/ 은 분류기, chroma_db/ 는 챗봇 검색에 필요)

## 제출 전 자체 검증

```bash
bash scripts/verify.sh              # 구조·양식만 (빠름, 모델 불필요)
bash scripts/verify.sh stub         # EXAONE 없이 파이프라인까지
bash scripts/verify.sh full         # 자산 복원 + 실제 출력 생성까지
```

## 제출물 패키징

코드만 담은 가벼운 제출 zip 생성(model/chroma 는 위 드라이브 링크로 복원):

```bash
TEAM=조이름 NAME=홍길동 bash scripts/package_submission.sh
# 실제 가중치(model.safetensors)까지 zip 에 동봉하려면:
INCLUDE_MODEL=1 TEAM=조이름 NAME=홍길동 bash scripts/package_submission.sh
```

`dist/Termproject_<NAME>/` 스테이징 폴더와 `dist/Termproject_<NAME>.zip` 이 생성됩니다. 런타임에 필요한 내부 패키지(`interface`, `retrieval`, `generation`, `embedding`, `crawlers`, `crawler_pipeline`)와 `restore_assets.sh` 가 함께 포함됩니다.
