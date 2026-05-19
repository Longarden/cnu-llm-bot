# CNU 학내정보 RAG 챗봇 Ver1

충남대학교 학생/교직원 대상 12개 카테고리 학내정보 RAG 챗봇.  
직접 크롤링한 데이터 + 하이브리드 검색(BM25 + BGE-M3 + RRF) + 환각 방지 5레이어.

## 아키텍처

- LLM: Qwen2.5-7B-Instruct-AWQ (4bit, ~5GB)
- 임베딩: BAAI/bge-m3 (~2GB)
- 벡터 DB: Chroma persistent
- 검색: BM25 sparse + BGE-M3 dense + Reciprocal Rank Fusion
- 추론 메모리 목표: < 12GB (Colab T4 15GB 한도)

## 설치

```bash
pip install -r requirements.txt
```

## 실행

```bash
# 크롤링
python -m crawlers

# 벡터 DB 구축
python -m embedding.vector_store

# Gradio UI 실행
python app/gradio_app.py
```

## 교수님 인터페이스

```python
from interface.answer_questions import answer_questions
answer_questions("data/sample_questions.jsonl", "data/sample_answers.jsonl")
```

## Google Colab 실행

1. `notebooks/main.ipynb` 열기
2. 런타임 → T4 GPU 선택
3. 셀 순서대로 실행 (예상 15~30분)

## 12개 카테고리

| ID | 카테고리 |
|----|---------|
| A | 시간성 (학식/도서관/셔틀) |
| B | 학사 (수강/졸업/일정) |
| C | 행정/증명서 |
| D | 장학/지원 |
| E | 취업/진로 |
| F | 학과 정보 |
| G | 학생 생활 |
| H | 캠퍼스 시설 |
| I | 국제/교환 |
| J | 비교과/대외활동 |
| K | 공지사항 |
| L | 학교 일반/소개 |
