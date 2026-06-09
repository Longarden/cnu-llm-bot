"""제출물 구조/양식 검증기 (순수 표준라이브러리 — torch/transformers 불필요, 즉시 실행).

조교가 받았을 때 기준으로:
  1) 필수 파일/폴더가 제 위치에 있는지 (PDF p20 빨간경로 + 런타임 패키지)
  2) outputs/*.json 이 공식 양식인지 (cls: id/question/label, chat·realtime: id/user/model)

사용:
  python scripts/verify_submission.py                      # 레포 루트 검사
  python scripts/verify_submission.py dist/Termproject_장정원   # 스테이징 폴더 검사
  python scripts/verify_submission.py dist/Termproject_장정원.zip  # zip 직접 검사
"""
import json
import os
import sys
import tempfile
import zipfile

# 윈도우 콘솔(cp949)에서도 한글/특수문자 출력이 깨지거나 죽지 않게 utf-8 고정.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

REQUIRED_FILES = [
    "data/test_cls.json",
    "data/test_chat.json",
    "src/classifier.ipynb",
    "chatbot.sh",
    "requirements.txt",
    "README.md",
]
# 챗봇 실행경로가 import 하는 런타임 패키지(하나라도 빠지면 chatbot.sh 가 깨짐)
REQUIRED_PKGS = ["src", "interface", "retrieval", "generation",
                 "embedding", "crawlers", "crawler_pipeline"]

OK = "[ OK ]"
NO = "[FAIL]"
WARN = "[WARN]"


def _exists(root, rel):
    return os.path.exists(os.path.join(root, rel))


def _check_cls(path, problems):
    rows = json.load(open(path, encoding="utf-8"))
    assert isinstance(rows, list) and rows, "리스트가 비어있음"
    for i, r in enumerate(rows):
        for k in ("id", "question", "label"):
            if k not in r:
                problems.append(f"cls_output[{i}] 키 누락: {k}")
        lab = r.get("label")
        if not isinstance(lab, int) or not (-1 <= lab <= 4):
            problems.append(f"cls_output[{i}] label 비정상: {lab} (0~4 또는 -1)")
    return len(rows)


def _check_chat(path, name, problems):
    rows = json.load(open(path, encoding="utf-8"))
    assert isinstance(rows, list) and rows, "리스트가 비어있음"
    for i, r in enumerate(rows):
        for k in ("id", "user", "model"):
            if k not in r:
                problems.append(f"{name}[{i}] 키 누락: {k}")
        if not str(r.get("model", "")).strip():
            problems.append(f"{name}[{i}] model 응답이 비어있음")
    return len(rows)


def verify(root: str) -> bool:
    print(f"\n=== 제출물 검증: {root} ===\n")
    problems = []

    print("[1] 필수 파일")
    for rel in REQUIRED_FILES:
        ok = _exists(root, rel)
        print(f"  {OK if ok else NO} {rel}")
        if not ok:
            problems.append(f"필수 파일 누락: {rel}")

    print("\n[2] 런타임 패키지(챗봇 import 의존)")
    for pkg in REQUIRED_PKGS:
        ok = os.path.isdir(os.path.join(root, pkg))
        print(f"  {OK if ok else NO} {pkg}/")
        if not ok:
            problems.append(f"런타임 패키지 누락: {pkg}/ (chatbot.sh 실행 불가)")

    print("\n[3] model/ 분류기 가중치")
    has_weight = _exists(root, "model/model.safetensors") or _exists(root, "model/model.bin")
    has_placeholder = _exists(root, "model/DOWNLOAD_MODEL.txt")
    has_cfg = _exists(root, "model/config.json") and _exists(root, "model/label_map.json")
    if has_weight and has_cfg:
        print(f"  {OK} 실제 가중치 동봉(model.safetensors/bin + config)")
    elif has_placeholder:
        print(f"  {WARN} 가중치는 드라이브 링크(placeholder). 채점 전 restore_assets.sh 로 복원 필요")
    else:
        print(f"  {NO} model/ 가중치도 placeholder도 없음")
        problems.append("model/ 가중치/placeholder 모두 없음 (분류기 로드 불가)")

    print("\n[4] outputs/ 출력 양식")
    checks = [
        ("outputs/cls_output.json", lambda p: _check_cls(p, problems)),
        ("outputs/chat_output.json", lambda p: _check_chat(p, "chat_output", problems)),
        ("outputs/realtime_output.json", lambda p: _check_chat(p, "realtime_output", problems)),
    ]
    for rel, fn in checks:
        full = os.path.join(root, rel)
        if not os.path.exists(full):
            print(f"  {WARN} {rel} 없음(채점 시 생성됨 — 동봉 안 해도 됨)")
            continue
        try:
            n = fn(full)
            print(f"  {OK} {rel} 양식 정상 ({n}건)")
        except Exception as e:
            print(f"  {NO} {rel} 파싱/양식 오류: {e}")
            problems.append(f"{rel} 양식 오류: {e}")

    print("\n=== 결과 ===")
    if problems:
        print(f"{NO} 문제 {len(problems)}건:")
        for p in problems:
            print(f"   - {p}")
        return False
    print(f"{OK} 모든 검사 통과 — 제출 구조/양식 OK")
    return True


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))

    if target.endswith(".zip"):
        with tempfile.TemporaryDirectory() as td:
            with zipfile.ZipFile(target) as z:
                z.extractall(td)
            # zip 안에 Termproject_* 단일 루트가 있으면 그 안으로
            entries = [os.path.join(td, e) for e in os.listdir(td)]
            roots = [e for e in entries if os.path.isdir(e)]
            root = roots[0] if len(roots) == 1 else td
            ok = verify(root)
    else:
        ok = verify(target)

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
