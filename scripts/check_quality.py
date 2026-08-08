"""메모/원본 데이터 품질 정량: 중국어 prefix % + 메뉴잡음 원본 %."""
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

FILES = [
    ROOT / 'data' / 'contextual_chunks.json',        # 600메모
    ROOT / 'data' / 'contextual_chunks_hier3b.json',  # 계층메모
]


def cjk_ratio(s):
    if not s:
        return 0
    return sum(1 for c in s if '一' <= c <= '鿿')


def is_menu_noise(body):
    """짧은 줄(메뉴 항목) 비율 높으면 메뉴 네비 잡음."""
    lines = [l.strip() for l in (body or '').split('\n') if l.strip()]
    if len(lines) < 5:
        return False
    short = sum(1 for l in lines if len(l) < 10)
    return short / len(lines) > 0.6


def main():
    for f in FILES:
        if not f.exists():
            print(f'{f.name}: 없음')
            continue
        d = json.load(open(f, encoding='utf-8'))
        tot = len(d)
        cjk = menu = 0
        for x in d:
            p = x.get('context_prefix', '') or ''
            if cjk_ratio(p) > 5:
                cjk += 1
            ot = x.get('original_text', '') or ''
            body = ot.replace(p, '', 1).strip() if p else ot
            if is_menu_noise(body):
                menu += 1
        print(f'{f.name}: 총 {tot} | 중국어prefix {cjk}({cjk/tot*100:.1f}%) | '
              f'메뉴잡음 {menu}({menu/tot*100:.1f}%)')


if __name__ == '__main__':
    main()
