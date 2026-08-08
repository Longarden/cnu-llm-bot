"""메모 후처리: 중국어 prefix 정리 + 메뉴잡음 청크 제거.

- 중국어 prefix(>5 한자): prefix 떼고 original_text를 원본만으로 복원 (청크는 유지)
- 메뉴잡음 원본(짧은줄 >60%): 청크 통째 제거 (운영시간 등 답 못 함)
백업 후 덮어쓰기. 두 메모 파일 각각.
"""
import sys, json, shutil
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

FILES = ['contextual_chunks.json', 'contextual_chunks_hier3b.json']


def cjk(s):
    return sum(1 for c in (s or '') if '一' <= c <= '鿿')


def is_menu(body):
    lines = [l.strip() for l in (body or '').split('\n') if l.strip()]
    if len(lines) < 5:
        return False
    return sum(1 for l in lines if len(l) < 10) / len(lines) > 0.6


def main():
    for name in FILES:
        f = ROOT / 'data' / name
        if not f.exists():
            print(f'{name}: 없음')
            continue
        d = json.load(open(f, encoding='utf-8'))
        shutil.copy(str(f), str(f) + '.prebak')
        out, rm_menu, fix_cjk = [], 0, 0
        for x in d:
            p = x.get('context_prefix', '') or ''
            ot = x.get('original_text', '') or ''
            body = ot.replace(p, '', 1).strip() if p else ot
            if is_menu(body):
                rm_menu += 1
                continue
            if cjk(p) > 5:
                x['context_prefix'] = ''
                x['original_text'] = body
                x['content'] = body
                fix_cjk += 1
            out.append(x)
        json.dump(out, open(f, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
        print(f'{name}: {len(d)} → {len(out)} | 메뉴제거 {rm_menu} | 중국어정리 {fix_cjk}')


if __name__ == '__main__':
    main()
