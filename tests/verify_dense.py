"""Phase A 진짜 검증: dense 임베딩 + Chroma 빌드 + 하이브리드 + 리랭커.
로컬 CPU 실행. bge-m3 첫 로드 시 2GB 다운로드.
출력은 UTF-8 파일로 (Windows 콘솔 cp949 회피)."""
import sys, io, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# UTF-8 출력 강제
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from embedding.data_loader import load_scoped_docs
from embedding.vector_store import build_vector_db, count
from retrieval import hybrid_retriever as hr

print("=== 1. 데이터 로드 ===")
docs = load_scoped_docs()
print(f"로드: {len(docs)}건")

print("=== 2. 벡터DB 빌드 (bge-m3 임베딩, CPU) ===")
build_vector_db(docs)
n = count()
print(f"Chroma 청크 수: {n}")
assert n >= 200, f"기대 200+ 실제 {n}"

print("=== 3. BM25 인덱스 ===")
hr.init_bm25_from_db()

print("=== 4. 하이브리드 검색 (BM25+dense+RRF) 진짜 검증 ===")
queries = ["오늘 학식 메뉴", "졸업 학점 몇학점", "국가장학금 신청 방법",
           "컴퓨터인공지능학부 교수님", "도서관 운영시간"]
for q in queries:
    res = hr.retrieve(q, n_results=3)
    print(f"\n[Q] {q} -> {len(res)} hits")
    for r in res[:3]:
        cat = r.get("data_category", "?")
        sp = r.get("sparse_score", 0.0)
        de = r.get("dense_score", 0.0)
        rrf = r.get("rrf_score", 0.0)
        txt = (r.get("original_text", "") or r.get("text", ""))[:55].replace("\n", " ")
        print(f"  ({cat}) sparse={sp:.2f} dense={de:.2f} rrf={rrf:.4f} | {txt}")

print("\n=== 5. 리랭커 (bge-reranker-v2-m3) 검증 ===")
try:
    os.environ["RERANK"] = "1"
    from retrieval.reranker import rerank
    q = "컴퓨터인공지능학부 교수님 연구실"
    cands = hr.retrieve(q, n_results=10)
    reranked = rerank(q, cands)
    print(f"리랭커 입력 {len(cands)} -> 출력 {len(reranked)}")
    for r in reranked[:3]:
        sc = r.get("rerank_score", r.get("score", 0.0))
        txt = (r.get("original_text", "") or r.get("text", ""))[:55].replace("\n", " ")
        print(f"  rerank={sc:.3f} | {txt}")
except Exception as e:
    print(f"리랭커 검증 실패: {type(e).__name__}: {e}")

print("\n=== DENSE 검증 완료 ===")
