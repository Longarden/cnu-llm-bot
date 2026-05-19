# 질문 풀 클러스터링: BGE-M3 임베딩 → KMeans 200 클러스터 → 대표 질문 추출

import json
import os
import numpy as np
from pathlib import Path
from typing import List, Dict


def cluster_questions(
    pool_path: str = None,
    output_path: str = None,
    n_clusters: int = 200,
) -> List[Dict]:
    """질문 풀을 클러스터링해서 대표 질문 추출"""
    base = Path(__file__).parent.parent

    if pool_path is None:
        pool_path = str(base / "data" / "questions" / "question_pool.jsonl")
    if output_path is None:
        output_path = str(base / "data" / "questions" / "clustered_representatives.jsonl")

    questions = _load_pool(pool_path)
    if not questions:
        print("질문 풀이 비어 있습니다.")
        return []

    texts = [q["question"] for q in questions]
    print(f"총 {len(texts)}개 질문 임베딩 중...")

    embeddings = _embed(texts)
    print(f"임베딩 완료. 클러스터링 ({n_clusters}개)...")

    labels = _kmeans(embeddings, n_clusters=min(n_clusters, len(texts)))
    representatives = _pick_representatives(questions, embeddings, labels)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for item in representatives:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    print(f"대표 질문 {len(representatives)}개 저장 → {output_path}")
    return representatives


def _load_pool(path: str) -> List[Dict]:
    items = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    items.append(json.loads(line))
    except FileNotFoundError:
        print(f"파일 없음: {path}")
    return items


def _embed(texts: List[str]) -> np.ndarray:
    """BGE-M3로 임베딩. 불가능하면 TF-IDF 폴백."""
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("BAAI/bge-m3")
        return model.encode(texts, batch_size=32, show_progress_bar=True, normalize_embeddings=True)
    except Exception as e:
        print(f"BGE-M3 로드 실패: {e} → TF-IDF 폴백")
        from sklearn.feature_extraction.text import TfidfVectorizer
        vec = TfidfVectorizer(max_features=1024)
        return vec.fit_transform(texts).toarray()


def _kmeans(embeddings: np.ndarray, n_clusters: int) -> np.ndarray:
    from sklearn.cluster import KMeans
    km = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    return km.fit_predict(embeddings)


def _pick_representatives(questions: List[Dict], embeddings: np.ndarray, labels: np.ndarray) -> List[Dict]:
    """각 클러스터에서 centroid에 가장 가까운 질문 1개 선택"""
    from sklearn.metrics.pairwise import cosine_similarity

    cluster_ids = np.unique(labels)
    representatives = []

    for cid in cluster_ids:
        idxs = np.where(labels == cid)[0]
        cluster_embs = embeddings[idxs]
        centroid = cluster_embs.mean(axis=0, keepdims=True)
        sims = cosine_similarity(centroid, cluster_embs)[0]
        best = idxs[np.argmax(sims)]
        item = dict(questions[best])
        item["cluster_id"] = int(cid)
        representatives.append(item)

    return representatives


if __name__ == "__main__":
    cluster_questions()
