"""오늘 크롤(today_*.json) → all_dedup 통합 + 기존 chroma에 순수 증분 add (CPU). 삭제 0, 순증만.

전제: chroma_db/ 에 P100 풀빌드(22203청크)가 복원돼 있어야 함.

동작(절대 축소 안 함):
  1. data/crawled_staging/today_*.json 로드 + 품질게이트(6메타키/U+FFFD/len>=20). 신규 전부 유지.
  2. all_dedup 백업 후 신규 전부 append(기존 레코드 삭제 안 함).
  3. chroma: 옛 청크 삭제 없이, 신규 레코드만 청킹 → bge-m3(CPU) 임베딩 → add.
  4. count 검증(반드시 순증) + 샘플 쿼리.

재크롤 공지의 옛/새 약한 중복은 다음 풀리빌드의 최신우선 dedup이 정리(deduplicator.py).
실행: /c/Users/dmsak/miniconda3/python scripts/integrate_today_and_add.py
"""
import sys, os, io, json, glob
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
except Exception:
    pass

ALL = os.path.join(ROOT, "data", "crawled", "all_dedup.json")
STG = os.path.join(ROOT, "data", "crawled_staging")
REQ_META = ["source_url", "data_category", "last_crawled_at", "valid_until", "freshness_tier", "original_text"]


def valid(r):
    if not all(k in r for k in REQ_META):
        return False
    blob = (r.get("original_text", "") or "") + (r.get("title", "") or "")
    if "�" in blob:
        return False
    return len(str(r.get("original_text", "")).strip()) >= 20


def main():
    print("=== 1. 오늘 크롤 staging 로드(신규 전부 유지) ===")
    new_records = []
    for f in sorted(glob.glob(os.path.join(STG, "today_*.json"))):
        recs = json.load(open(f, encoding="utf-8"))
        good = [r for r in recs if valid(r)]
        print(f"  {os.path.basename(f)}: {len(recs)} → 유효 {len(good)}")
        new_records.extend(good)
    if not new_records:
        print("신규 0건 → 종료"); return
    from collections import Counter
    print(f"신규 유효 총 {len(new_records)}건  카테고리: {dict(Counter(r['data_category'] for r in new_records))}")

    print("=== 2. all_dedup 백업 + 신규 전부 append(삭제 0) ===")
    dd = json.load(open(ALL, encoding="utf-8"))
    bak = ALL + f".today_bak_{date.today().isoformat()}"
    if not os.path.exists(bak):
        json.dump(dd, open(bak, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    merged = dd + new_records
    json.dump(merged, open(ALL, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"  all_dedup {len(dd)} → {len(merged)} (신규 +{len(new_records)}, 삭제 0)")

    print("=== 3. chroma 열기(삭제 없음) ===")
    import chromadb
    from embedding.chunker import chunk_documents
    col = chromadb.PersistentClient(path=os.path.join(ROOT, "chroma_db")) \
        .get_or_create_collection("cnu_rag", metadata={"hnsw:space": "cosine"})
    before = col.count()
    print(f"  현재 청크수: {before}")

    print("=== 4. 신규 전부 청킹 + bge-m3(CPU) 임베딩 + add ===")
    chunks = chunk_documents(new_records)
    texts, metas, ids = [], [], []
    stamp = date.today().isoformat().replace("-", "")
    for i, doc in enumerate(chunks):
        t = doc.get("original_text", "")
        if not t:
            continue
        metas.append({k: str(doc.get(k, "")) for k in REQ_META})
        texts.append(t)
        ids.append(f"today{stamp}_{i}")
    print(f"  신규 청크 {len(texts)}개 임베딩 중(bge-m3, CPU)…")
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("BAAI/bge-m3")
    emb = model.encode(texts, batch_size=32, normalize_embeddings=True, show_progress_bar=True).tolist()
    for s in range(0, len(texts), 500):
        col.add(documents=texts[s:s+500], embeddings=emb[s:s+500], metadatas=metas[s:s+500], ids=ids[s:s+500])
    final = col.count()
    sign = "+" if final >= before else ""
    print(f"=== 완료. 청크수 {before} → {final} (순증 {sign}{final-before}) ===")
    if final < before:
        print("  [경고] 순증이 음수! 예상과 다름 — 확인 필요")

    print("=== 5. 샘플 쿼리 검증 ===")
    for q in ["이번주 학식 메뉴", "셔틀버스 운행 시간", "기말고사 성적 공지", "계절학기 폐강"]:
        qe = model.encode([q], normalize_embeddings=True).tolist()
        res = col.query(query_embeddings=qe, n_results=2)
        print(f"  Q: {q}")
        for m in res["metadatas"][0]:
            print("     -", m.get("data_category"), "|", (m.get("original_text", "")[:46]).replace("\n", " "))


if __name__ == "__main__":
    main()
