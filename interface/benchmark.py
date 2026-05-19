"""추론 속도 + GPU 메모리 벤치마크 (AC14)."""

import json
import time
from pathlib import Path
from typing import Union


def benchmark_inference(
    testset: Union[list[dict], str],
    n: int = 50,
    output_path: str = "data/benchmark.json",
) -> dict:
    """
    Args:
        testset: 질문 dict 리스트 또는 JSONL 파일 경로
        n: 벤치마크할 질문 수
        output_path: 결과 저장 경로

    Returns:
        {"avg_latency_ms", "p50_latency_ms", "p95_latency_ms", "gpu_memory_peak_mb", "n"}
    """
    from interface.answer_questions import _rag_answer
    from generation.llm import print_gpu_memory

    # testset 이 파일 경로인 경우 로드
    if isinstance(testset, str):
        from interface.answer_questions import _load_questions
        testset = _load_questions(testset)

    subset = testset[:n]

    # GPU 메모리 초기화
    gpu_peak_mb = 0.0
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
    except ImportError:
        pass

    print_gpu_memory()
    latencies = []

    for item in subset:
        question = item.get("question", item.get("q", ""))
        start = time.perf_counter()
        try:
            _rag_answer(question)
        except Exception as e:
            print(f"[benchmark] 실패: {e}")
        elapsed_ms = (time.perf_counter() - start) * 1000
        latencies.append(elapsed_ms)
        print(f"  {question[:40]}: {elapsed_ms:.0f}ms")

    # 통계 계산
    if latencies:
        sorted_lat = sorted(latencies)
        avg = sum(latencies) / len(latencies)
        p50 = sorted_lat[len(sorted_lat) // 2]
        p95 = sorted_lat[min(int(len(sorted_lat) * 0.95), len(sorted_lat) - 1)]
    else:
        avg = p50 = p95 = 0.0

    # GPU 피크 메모리
    try:
        import torch
        if torch.cuda.is_available():
            gpu_peak_mb = torch.cuda.max_memory_allocated() / 1024**2
        else:
            gpu_peak_mb = 0.0
    except ImportError:
        gpu_peak_mb = 0.0

    result = {
        "n": len(latencies),
        "avg_latency_ms": round(avg, 1),
        "p50_latency_ms": round(p50, 1),
        "p95_latency_ms": round(p95, 1),
        "gpu_memory_peak_mb": round(gpu_peak_mb, 1),
    }

    print(f"\n[benchmark] avg={avg:.0f}ms | p50={p50:.0f}ms | p95={p95:.0f}ms | gpu_peak={gpu_peak_mb:.0f}MB")
    print_gpu_memory()

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return result
