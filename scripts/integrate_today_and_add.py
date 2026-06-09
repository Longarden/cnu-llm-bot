"""오늘 크롤(today_*.json) → all_dedup 통합 + 기존 chroma에 증분 add (CPU). 순증만(축소 금지).

전제: chroma_db/ 에 P100 풀빌드(22203청크)가 복원돼 있어야 함.

동작:
  1. data/crawled_staging/today_*.json 모두 로드 + 품질게이트(6메타키/U+FFFD/len>=20). 신규 전부 유지.
  2. URL이 신규에서 '정확히 1번'만 나오는 것 = 진짜 재크롤(공지 등) → 그 URL의 옛 레코드/청크만 교체.
     같은 URL에 여러 건(식단 일자별 등)은 교체 안 하고 그대로 추가(붕괴/축소 방지).
  3. all_dedup 백업 후: single_urls 옛 레코드 제거 + 신규 전부 append.
  4. chroma: single_urls 옛 청크 삭제 → 신규 전부 청킹 → bge-m3(CPU) 임베딩 → add.
  5. count 검증(순증 확인) + 샘플 쿼리.

실행: /c/Users/dmsak/miniconda3/python scripts/integrate_today_and_add.py
"""
import sys, os, io, json, glob
from collections import Counter
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
    print(f"신규 유효 총 {len(new_records)}건")

    # URL이 신규에서 정확히 1번만 나오는 것 = 진짜 재크롤(교체 대상). 여러 건 URL은 추가만.
    urlc = Counter(r.get("source_url", "") for r in new_records if r.get("source_url"))
    single_urls = {u for u, c in urlc.items() if c == 1 and u}
    print(f"교체 대상(단일레코드 URL=재크롤): {len(single_urls)} / 추가만 할 다건 URL: {sum(1 for c in urlc.values() if c>1)}")

    print("=== 2. all_dedup 백업 + 갱신(신규 전부 append) ===")
    dd = json.load(open(ALL, encoding="utf-8"))
    bak = ALL + f".today_bak_{date.today().isoformat()}"
    if not os.path.exists(bak):
        json.dump(dd, open(bak, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    kept = [r for r in dd if r.get("source_url", "") not in single_urls]
    merged = kept + new_records
    json.dump(merged, open(ALL, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"  all_dedup {len(dd)} → {len(merged)} (재크롤 교체로 제거 {len(dd)-len(kept)}, 신규 +{len(new_records)})")

    print("=== 3. chroma 열기 + 재크롤 URL 옛 청크만 삭제 ===")
    import chromadb
    from embedding.chunker import chunk_documents
    col = chromadb.PersistentClient(path=os.path.join(ROOT, "chroma_db")) \
        .get_or_create_collection("cnu_rag", metadata={"hnsw:space": "cosine"})
    before = col.count()
    print(f"  현재 청크수: {before}")
    su = [u for u in single_urls if u]
    for i in range(0, len(su), 200):
        try:
            col.delete(where={"source_url": {"$in": su[i:i+200]}})
        except Exception as e:
            print(f"  (삭제 스킵: {e})")
    after_del = col.count()
    print(f"  재크롤 옛 청크 삭제 후: {after_del} (삭제 {before-after_del})")

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
    print(f"=== 완료. 청크수 {before} → {final} (순증 {final-before:+d}) ===")

    print("=== 5. 샘플 쿼리 검증 ===")
    for q in ["이번주 학식 메뉴", "셔틀버스 운행 시간", "기말고사 성적 공지"]:
        qe = model.encode([q], normalize_embeddings=True).tolist()
        res = col.query(query_embeddings=qe, n_results=2)
        print(f"  Q: {q}")
        for m in res["metadatas"][0]:
            print("     -", m.get("data_category"), "|", (m.get("original_text", "")[:46]).replace("\n", " "))


if __name__ == "__main__":
    main()
