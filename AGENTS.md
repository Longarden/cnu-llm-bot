# AGENTS.md - CNU 학내정보 RAG 챗봇 Ver1

## 프로젝트 개요

충남대학교 학생/교직원 대상 12개 카테고리(시간성·학사·행정·장학·취업·학과·학생생활·시설·국제·비교과·공지·학교소개) 질문에 환각 없이 답변하는 RAG 챗봇.

## 스택

- LLM: Qwen2.5-7B-Instruct-AWQ (4bit, 5~6GB)
- 임베딩: BAAI/bge-m3 (한국어 강함, 2GB)
- 벡터 DB: Chroma persistent (1~2GB)
- 검색: BM25(rank_bm25) + BGE-M3 dense + Reciprocal Rank Fusion (k=60)
- 리랭커: BAAI/bge-reranker-v2-m3 (선택, RERANK=1 env)
- 크롤러: Crawl4AI + BeautifulSoup4
- Distillation: Claude Haiku API (DISTILL=1 env)
- 평가: Claude Sonnet API (LLM-as-judge)
- UI: Gradio (share=True 시연용)
- 추론 총 메모리: 8~11GB / 15GB 한도

## 5레이어 환각 방지

1. Freshness 메타데이터 (source_url, data_category, last_crawled_at, valid_until, freshness_tier, original_text)
2. Time-aware retrieval (한국어 날짜 NER + 메타데이터 필터)
3. 출처 강제 명시 (답변마다 출처: URL 업데이트: 날짜)
4. 거절 메커니즘 (검색 점수 < 0.6 또는 stale → 거절)
5. 시스템 프롬프트 + few-shot 5개 (컨텍스트만 사용, 추측 금지)

## 디렉토리 역할

| 디렉토리 | 역할 |
|---------|------|
| crawlers/ | 12개 카테고리 크롤러 (base.py 상속, _fallback() 구현 필수) |
| crawler_pipeline/ | Crawl4AI 래퍼, Claude Haiku distiller, 중복 제거 |
| embedding/ | BGE-M3 임베딩, 청킹(400/50), Chroma 벡터 DB |
| retrieval/ | 한국어 날짜 NER, 카테고리 라우터, 하이브리드 검색, 리랭커 |
| generation/ | Qwen2.5-7B-AWQ 로드, 시스템 프롬프트, 거절 로직 |
| question_generation/ | Claude Sonnet으로 1만 질문 생성, KMeans 클러스터 |
| eval/ | 평가셋 200개 추출, LLM-as-judge, 전체 평가 실행 |
| interface/ | 교수님 제출 인터페이스(answer_questions), 벤치마크 |
| app/ | Gradio 시연 UI |
| notebooks/ | Colab 마스터 노트북 (main.ipynb) |
| data/ | 크롤 결과, distilled 결과, 질문 풀, 평가셋 |
| chroma_db/ | Chroma persistent 스토리지 |
| tests/ | 단위 테스트 (date_extractor 8패턴 등) |

## 제출 인터페이스

```python
from interface.answer_questions import answer_questions
answer_questions("questions.jsonl", "answers.jsonl")
```

## 환경 변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| DISTILL | 0 | 1이면 Claude Haiku distillation 활성화 |
| RERANK | 0 | 1이면 BGE-reranker 활성화 |
| CACHED | 0 | 1이면 크롤 없이 data/crawled/*.json 캐시 로드 |
| MODEL_FALLBACK | 7b | 3b이면 Qwen2.5-3B 폴백 |
| ANTHROPIC_API_KEY | - | Claude API 키 |
