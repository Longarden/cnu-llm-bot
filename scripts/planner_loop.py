"""4 워커 done 감지 + sweep 큐 처리 (무한 보충, stop 파일로 종료)."""
import sys, time, subprocess
from pathlib import Path
from datetime import datetime

ROOT = Path('C:/Users/dmsak/cnu-llm-bot')
STAGING = ROOT / 'data/crawled_staging'
PLANNER = ROOT / 'data/planner'
STOP = PLANNER / 'stop'
SEEDS = PLANNER / 'sweep_seeds.txt'
SWEEP_DONE_FILE = PLANNER / 'sweep_done.txt'
LOG = PLANNER / 'progress.log'

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

WORKERS = ['dept_full_v2', 'regulations_v2', 'admission_v2', 'life_v2']
MAX_CONCURRENT_SWEEP = 2
POLL_INTERVAL = 30  # 초
SWEEP_PYTHON = 'C:/Users/dmsak/miniconda3/python.exe'


def log(msg):
    line = f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] {msg}'
    print(line, flush=True)
    PLANNER.mkdir(parents=True, exist_ok=True)
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(line + '\n')


def v1_status():
    done = [w for w in WORKERS if (STAGING / f'{w}.done').exists()]
    pending = [w for w in WORKERS if w not in done]
    return done, pending


def load_seeds():
    if not SEEDS.exists():
        return []
    items = []
    for line in SEEDS.read_text(encoding='utf-8').splitlines():
        s = line.strip()
        if not s or s.startswith('#'):
            continue
        parts = s.split()
        if len(parts) < 2:
            continue
        host = parts[0]
        cat = parts[1]
        mx = parts[2] if len(parts) >= 3 else '150'
        items.append((host, cat, mx))
    return items


def loaded_done():
    if not SWEEP_DONE_FILE.exists():
        return set()
    return set(l.strip() for l in SWEEP_DONE_FILE.read_text(encoding='utf-8').splitlines() if l.strip())


def mark_done(host):
    with open(SWEEP_DONE_FILE, 'a', encoding='utf-8') as f:
        f.write(host + '\n')


def check_stop():
    return STOP.exists()


def phase1_wait():
    """4 워커 모두 done 될 때까지 대기."""
    while True:
        if check_stop():
            log('stop 감지 → planner 종료')
            return False
        done, pending = v1_status()
        if not pending:
            log(f'phase1 완료: 4 워커 모두 done ({", ".join(done)})')
            return True
        log(f'phase1 대기 — done={done} pending={pending}')
        time.sleep(POLL_INTERVAL)


def phase2_sweep():
    """sweep 큐 처리. 최대 N개 병렬, 큐 소진까지."""
    log('=== phase 2 시작: 도메인 sweep ===')
    running = {}
    while True:
        if check_stop():
            log('stop 감지 → sweep 모두 종료')
            for host, p in running.items():
                try:
                    p.terminate()
                except Exception:
                    pass
            return

        finished = []
        for host, p in running.items():
            if p.poll() is not None:
                finished.append(host)
                log(f'sweep 완료: {host} (exit={p.returncode})')
                mark_done(host)
        for h in finished:
            running.pop(h, None)

        seeds = load_seeds()
        done = loaded_done()
        todo = [s for s in seeds if s[0] not in done and s[0] not in running]

        if not todo and not running:
            log('큐 소진 + 진행 중 없음 → planner 정상 종료')
            return

        while len(running) < MAX_CONCURRENT_SWEEP and todo:
            host, cat, mx = todo.pop(0)
            log_path = PLANNER / f'sweep_{host.replace(".", "_")}.log'
            log(f'sweep 시작: {host} cat={cat} max={mx} → {log_path.name}')
            with open(log_path, 'w', encoding='utf-8') as lf:
                p = subprocess.Popen(
                    [SWEEP_PYTHON,
                     str(ROOT / 'scripts/crawl_workers/worker_sweep.py'),
                     host, cat, str(mx)],
                    stdout=lf, stderr=subprocess.STDOUT,
                    cwd=str(ROOT),
                )
            running[host] = p

        if running:
            log(f'진행 중: {", ".join(running)} ({len(running)}/{MAX_CONCURRENT_SWEEP})')
        time.sleep(POLL_INTERVAL)


def main():
    log('=' * 50)
    log('planner_loop 시작')
    if not phase1_wait():
        return
    phase2_sweep()
    log('planner_loop 정상 종료')


if __name__ == '__main__':
    main()
