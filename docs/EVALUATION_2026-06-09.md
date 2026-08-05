# cnu-llm-bot 종합 평가 (2026-06-09, 마감 D-3)

평가 대상: C:\Users\dmsak\cnu-llm-bot (사용자 실제 파이프라인)
기준: 2026 자연어처리 텀프 공식 스펙 + 더미 제출 계약
방식: 정적 코드 분석 4개 병렬 리뷰 + 직접 교차검증 (로컬 CPU라 실행 미수행)

---

## 0. 한 줄 결론

엔지니어링은 학부 텀프 기준 과할 만큼 잘 만들었다(분류기 + 하이브리드RAG + CRAG + 라이브크롤 + Gradio + 패키저).
그런데 **제출 배관(가중치/벡터DB를 Colab으로 보내는 경로)이 미완성**이고, **채점 런타임 경로에서 BM25·리랭커가 꺼져** 자랑하던 하이브리드가 dense-only로 퇴화한다.
잠재력과 현재 제출본 사이 격차가 매우 크지만, 전부 3일 안에 고칠 수 있다.

---

## 1. 점수 예측 (130점 = 분류기40 + 챗봇UI60 + 실시간30옵션)

| 컴포넌트 | 현재 제출본 그대로 | 3일 액션 후 | 만점 | 0점/감점 원인 |
|---|---|---|---|---|
| Task1 분류기 (F1) | 0 | 36~40 | 40 | 가중치가 Colab에 안 감 → 노트북 크래시 |
| Task2 챗봇+UI | 0~20 | 50~58 | 60 | 벡터DB/가중치 없음 → 전부 "정보 못 찾음" |
| Task3 실시간 (옵션) | 0 | 20~27 | 30 | 분류기 로드 실패 시 동반 크래시 |
| 합계 | 약 0~20 | 약 106~125 | 130 | — |

핵심 메시지: 코드 실력이 아니라 "제출 마무리"에서 점수가 통째로 샌다.

---

## 2. 치명 결함 3가지 (이거 안 고치면 0점)

### 치명-1. 가중치·벡터DB가 Colab에 도달하지 못함
- restore_assets.sh:11-12 → MODEL_ID="YOUR_MODEL_TAR_GZ_FILE_ID", CHROMA_ID="YOUR_CHROMA_TAR_GZ_FILE_ID" (placeholder 그대로, dist/Termproject_장정원 패키지도 동일)
- dist/Termproject_장정원/model/DOWNLOAD_MODEL.txt:7 → "<model.tar.gz 공유 링크>" (미기입)
- 로컬엔 진짜 자산 존재: model/model.safetensors 422MB, chroma_db 13MB(41파일). 하지만 zip엔 제외됨.
- 결과: 채점 Colab에서 model/ 비면 classifier.ipynb의 from_pretrained가 OSError → Task1 0점. chroma_db 비면 RAG가 전부 거절 → Task2 응답 0점.
- restore_assets.sh:8 set -euo pipefail → gdown 실패 시 즉시 중단(부분복원도 안 됨).

### 치명-2. 채점 경로에서 하이브리드 검색이 dense-only로 퇴화
- BM25 초기화 init_bm25_from_db()는 notebooks/tests에서만 호출. 채점 경로(src/chat_pipeline.py, src/gen_chat_output.py, interface/answer_questions.py)에서 호출 안 함.
- 결과: retrieval/hybrid_retriever.py:217-218 에서 _bm25 is None → sparse 검색이 빈 리스트 → "BM25+dense+RRF 하이브리드"가 조용히 dense-only로 작동. 에러도 안 남.
- 영향: "졸업학점", 정확 키워드(과목코드/건물명) 매칭 recall 저하 → 졸업요건·공지 응답 품질 하락.

### 치명-3. 리랭커 OFF → CRAG 3밴드 거절게이트가 죽은 코드
- retrieval/reranker.py:29 → RERANK 기본 "0". chatbot.sh는 RERANK 미export(.env.example엔 1이지만 source 안 함).
- 결과: rerank_score가 안 채워짐 → generation/rejector.py:152-189 CRAG 3밴드가 한 번도 실행 안 됨. 설계서의 핵심 자랑(CRAG)이 채점 경로에서 무효.

---

## 3. 컴포넌트별 상세

### Task1 분류기 (40점) — 코드는 정상, 배관만 문제
- 정확성 OK: classifier.ipynb cell-4가 {"id": get('id', i), "question": q, "label": int(argmax)} 생성. id 없으면 인덱스, label 정수 보장. test_cls.json 경로 정확.
- 학습/추론 일치 OK: 학습 raw 정수라벨, 추론 argmax 인덱스=과제라벨. 순서 뒤바뀜 위험 없음.
- 주의: data/cls/valid.json이 data/test_cls.json과 100% 동일 → 보고된 검증성능은 과대평가(실측 held-out 없음). 실제 F1은 확인불가.
- 예상 F1: 낙관 0.95~1.0(키워드 분리 쉬움), 비관 0.80~0.90(라벨1 공지가 타클래스와 키워드 중첩).
- 문서 불일치: README "klue/bert-base" vs config "klue/roberta-base" vs COLAB_RUN "klue/roberta-large". 채점 무관하나 발표 신뢰도 하락.

### Task2 챗봇+UI (60점) — 구조 탄탄, 자산·배관이 발목
- UI: src/chatbot_ui.py가 Gradio Blocks로 입력/응답/대화흐름/스트리밍/분류뱃지까지 실제 구현. GRADIO_SHARE=1로 Colab .gradio.live 링크 발급. (장정원 패키지 chatbot_ui.py 8.8KB=풀버전, 홍길동판은 2.1KB 스텁)
- 형식 10점: chat_output.json {"id","user","model"} 스펙 일치, model은 항상 문자열(생성 실패해도 "생성 오류:..." 채움) → 형식 안전.
- 응답 40점: 하이브리드→리랭커→CRAG→로컬생성 흐름은 좋으나 치명-2/3로 절반만 작동. 거절게이트는 ALWAYS_ANSWER=1이라 과소거절(환각 위험 있으나 정성평가엔 유리).
- 코퍼스: 런타임 코퍼스 all_dedup.json은 본문 풀텍스트 보유(과거 "공지 제목만" 이슈는 해소). 식단 메뉴/셔틀 시간표/학과 본문 실재.
- 생성모델: generation/llm.py 기본 EXAONE-3.5-7.8B(4bit) vs 문서 Qwen2.5-7B → 불일치. T4 로드 실측 확인불가.

### Task3 실시간 (30점 옵션) — 진짜 라이브크롤, 폴백 견고
- realtime_model.py가 label 1/3/4를 notices/dining/shuttle 라이브 크롤. 포맷 {"id","user","model"} 일치.
- is_fallback 마킹으로 더미 데이터를 "라이브"로 위장 안 함 → 정직한 설계(학부생이 잘 안 하는 디테일).
- 리스크: 식단/공지 크롤이 사이트 HTML 셀렉터 의존 → 채점일 사이트 지연/개편이면 0건→폴백 메시지. 네트워크 실패해도 포맷은 안 깨짐.

### 제출/실행 안전성
- 좋음: chatbot.sh가 set -e 없이 단계별 || echo로 비차단 → JSON 생성 실패해도 UI는 뜸(데모 안전). classifier.ipynb에 drive.mount/하드코딩 경로 없음 → 채점환경 친화적.
- 나쁨: dist에 Termproject_장정원(신, 올바른 이름)과 Termproject_홍길동(구, 432바이트 placeholder model.bin, 스텁 UI) 공존 → 잘못된 zip 제출 위험. 홍길동 폐기 필요.
- 제출 zip이 코드만 담는 방식이면 model/·chroma_db/ 복원이 유일한 생명선인데 그 링크가 미기입(치명-1).

---

## 4. 코드 품질 / 아키텍처

엔지니어링 성숙도: 6.5/10 (모듈 분리·방어적 진입점은 강점, 문서/런타임 드리프트와 죽은 핵심기능이 깎음)

강점
- retrieval/generation/embedding/crawlers 모듈 경계 깔끔(단일책임).
- chatbot.sh 비차단 설계, _rag_answer try/except 폴백.
- is_fallback 규율(더미 데이터 위장 방지).
- requirements.txt에 의존성 핀 이유를 주석으로 설명(transformers<4.49 / torch2.5.1 / CVE-2025-32434 .bin 회피).
- ROOT 자동탐색이 노트북·CLI 양쪽에서 동작.

과설계 vs 실효 (채점 기준 기준)

| 기능 | 채점 경로 기본 | 채점 기여 | 권고 |
|---|---|---|---|
| BM25 하이브리드 | OFF(미초기화) | 현재 0 | 켜라(1줄) 또는 문서에서 빼라 |
| 리랭커 | OFF(RERANK 미설정) | 현재 0 | 켜라 또는 문서에서 빼라 |
| CRAG 3밴드 | OFF(리랭커 의존) | 현재 0 | 리랭커 켜면 살아남 |
| crag_escalation/contextual_chunker/query_transform/metadata_boost | OFF(스크립트만) | 0 | 레포 보존, 제출 zip엔 제외 |
| question_generation/, eval/, self_verify | OFF | 0 | 제출 zip 제외 |
| ALWAYS_ANSWER 소프트거절 | ON | 높음(정성평가 유리) | 유지 |
| 식단/셔틀 라이브크롤 | ON | 높음(Task3) | 유지 + 캐시폴백 고려 |

죽은/잡파일(제출 제외 대상): 루트 _probe2.py, _probe_extra_notices.py, _final_samples.txt, _ub_run2.log, _ub_attach_computer_report.json, CUsersdmsak...todo_list.txt, dist/Termproject_홍길동.

---

## 5. 마감 전 우선순위 액션 (3일, 점수영향 순)

1. [치명, 최우선] 자산 배포·복원 확정 (이거 안 하면 나머지 다 무의미)
   - model.tar.gz(safetensors+config+tokenizer), chroma_db.tar.gz를 구글드라이브 업로드("링크 있는 모두: 뷰어").
   - restore_assets.sh:11-12 MODEL_ID/CHROMA_ID에 실제 파일ID 기입. DOWNLOAD_MODEL.txt 링크도 기입.
   - 또는 INCLUDE_MODEL=1로 가중치를 zip에 직접 동봉(용량 허용 시 가장 안전).
2. [치명, 1줄씩] 채점 경로에서 검색 정직화
   - src/chat_pipeline.py 또는 진입부에 init_bm25_from_db() 한 번 호출 → 하이브리드 복구.
   - chatbot.sh에 export RERANK=1 추가 → 리랭커+CRAG 정상화. (단 T4 메모리/속도 재확인. 불안하면 dense-only로 두되 README/AGENTS에서 "하이브리드+CRAG" 표현을 사실대로 수정.)
3. [높음] 제출 zip 재생성 + 잡파일 제거
   - NAME=장정원 (필요시 INCLUDE_MODEL=1) bash scripts/package_submission.sh로 신버전 chatbot.sh·올바른 이름 반영.
   - dist/Termproject_홍길동, 루트 _*.py/_*.log/_*.txt, scripts/·eval/·notebooks/·question_generation/ 제출 제외.
4. [중간] 문서 3종 통일: 분류기=klue/roberta-base, 생성=EXAONE-3.5-7.8B 4bit(local)로 README/AGENTS/COLAB_RUN/llm.py 주석 정정. "본인 시스템도 모른다" 인상 제거.
5. [중간] 실측 F1 확보: held-out(valid≠test) 셋으로 분류기 F1 측정·문서화(현재 valid=test라 과대).

---

## 6. Colab 스모크 체크리스트 (6/12 전 새 노트북에서 1회 끝까지)

- [ ] git clone → bash restore_assets.sh → model/ 와 chroma_db/ 실제로 생기는지(placeholder면 여기서 멈춤)
- [ ] src/classifier.ipynb 위에서부터 무중단 실행 → outputs/cls_output.json에 label 0~4 정수 생성 확인
- [ ] bash chatbot.sh → outputs/chat_output.json 16건(스텁 아님) + .gradio.live 링크
- [ ] UI에서 졸업/공지/학사일정/식단/셔틀 5유형 질문 → 거절 없이 실응답 + 분류뱃지(빈응답이면 자산복원 실패 신호)
- [ ] python src/realtime_model.py → realtime_output.json에 오늘자 라이브 데이터(폴백 도배 아님)
- [ ] EXAONE 7.8B가 T4에서 OOM 없이 로드되는지(안 되면 fallback 모델로 안전화)

---

## 확인불가 (실행 불가로 코드흐름 추론만)
- 실제 F1 수치, EXAONE 7.8B의 T4 실로드, chroma_db 청크 수, 채점 사이트 크롤 응답성, 채점자가 zip-only인지 clone방식인지. → 모두 위 6번 Colab 검증으로 해소.
