"""단일 프로세스 실행기: chat 배치 + realtime 배치 + UI 를 '한 프로세스'에서 순차 실행.

기존 chatbot.sh 는 python 을 3번(gen_chat_output / realtime_model / chatbot_ui) 따로 호출해
생성모델(EXAONE 7.8B)을 3번 로드했다(콜랩에서 로딩만 회당 ~2.5분 → 5분 낭비 + 포트/GPU 충돌).
여기서는 한 프로세스라 generation.llm._llm_pipeline 싱글톤이 공유되어 7B 가 '1회'만 로드된다.

이미 outputs/chat_output.json·realtime_output.json 이 있으면 해당 배치는 건너뛴다(FORCE_BATCH=1 로 강제).
실행: python src/run_all.py   (chatbot.sh 가 호출)
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

FORCE = os.environ.get("FORCE_BATCH", "0") == "1"


def _has(name: str) -> bool:
    p = ROOT / "outputs" / name
    return p.exists() and p.stat().st_size > 0


# (1) Task2 chat 배치 — 여기서 7B 최초 1회 로드(이후 모두 재사용)
if FORCE or not _has("chat_output.json"):
    print("[run_all] (1) chat 배치 → outputs/chat_output.json")
    try:
        import src.gen_chat_output as _g
        _g.main()
    except Exception as e:
        print(f"[run_all] (1) chat 경고(계속 진행): {e}")
else:
    print("[run_all] (1) outputs/chat_output.json 있음 — 배치 건너뜀(FORCE_BATCH=1 로 재생성)")

# (2) Task3 realtime 배치 — 같은 프로세스 → 7B 재로딩 없음
if FORCE or not _has("realtime_output.json"):
    print("[run_all] (2) realtime 배치 → outputs/realtime_output.json")
    try:
        import src.realtime_model as _r
        _r.main()
    except Exception as e:
        print(f"[run_all] (2) realtime 경고(계속 진행): {e}")
else:
    print("[run_all] (2) outputs/realtime_output.json 있음 — 배치 건너뜀(FORCE_BATCH=1 로 재생성)")

# (3) UI — 같은 프로세스 → 7B 재로딩 없음. 워밍업도 이미 로드된 모델 재사용.
print("[run_all] (3) UI 실행 — 콜랩 좌측 '포트' 탭에서 7860")
from src.chatbot_ui import launch_app
launch_app()
