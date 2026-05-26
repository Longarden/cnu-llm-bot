"""학칙 + 입학처(ipsi.cnu.ac.kr) staging 수집기.

규칙:
- 학칙(rule) HWP: olefile + zlib + HWPTAG_PARA_TEXT 파싱 -> 텍스트
- 학칙 HTML 뷰(plus.cnu.ac.kr/_prog/rule/view_pop.php?mng_no=...) -> 보조 메타
- 입학처(ipsi.cnu.ac.kr): trafilatura(extract_main_text)
- 인코딩: 강제 utf-8 디코딩 후 text_repair.repair_encoding
- 출력: data/crawled_staging/regulations_admission.json (9키 dict 배열)
"""

from __future__ import annotations

import json
import re
import struct
import sys
import time
import zlib
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin

import requests

# Windows 콘솔 cp949 인코딩 문제 회피 (특수 유니코드 출력 무시)
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

ROOT = Path('C:/Users/dmsak/cnu-llm-bot')
sys.path.insert(0, str(ROOT))

from crawler_pipeline.body_extractor import extract_main_text  # noqa: E402
from crawler_pipeline.text_repair import repair_encoding  # noqa: E402

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
}

NOW = datetime.now()
VALID_UNTIL = (NOW + timedelta(days=90)).isoformat()
LAST_CRAWLED = NOW.isoformat()

OUT_PATH = ROOT / 'data' / 'crawled_staging' / 'regulations_admission.json'


# ---------------- 공통 유틸 ----------------

def safe_get(url: str, timeout: int = 25, retries: int = 2) -> bytes | None:
    last = None
    for _ in range(retries + 1):
        try:
            r = requests.get(url, headers=HEADERS, timeout=timeout)
            if r.status_code == 200 and r.content:
                return r.content
            last = f'status={r.status_code}'
        except Exception as e:
            last = str(e)
            time.sleep(0.6)
    print(f'  [WARN] safe_get fail {url}: {last}')
    return None


def fetch_utf8(url: str, timeout: int = 25) -> str | None:
    raw = safe_get(url, timeout=timeout)
    if raw is None:
        return None
    # 페이지가 명목상 latin1로 잡혀도 실제는 utf-8 (apparent_encoding=utf-8 확인 완료)
    try:
        return raw.decode('utf-8', errors='replace')
    except Exception:
        return raw.decode('cp949', errors='replace')


def make_doc(source_url: str, title: str, text: str, category: str) -> dict:
    text = repair_encoding(text.strip())
    return {
        'source_url': source_url,
        'data_category': category,
        'last_crawled_at': LAST_CRAWLED,
        'valid_until': VALID_UNTIL,
        'freshness_tier': 'semi_static',
        'original_text': text,
        'title': repair_encoding(title.strip()),
        'content': text,
        'date': NOW.strftime('%Y-%m-%d'),
    }


# ---------------- HWP 파싱 ----------------

def hwp_extract_text(hwp_bytes: bytes) -> str:
    """HWP 5.x OLE compound -> text. BodyText/SectionN -> HWPTAG_PARA_TEXT(0x43=67)."""
    try:
        import olefile
    except Exception:
        return ''
    try:
        ole = olefile.OleFileIO(BytesIO(hwp_bytes))
    except Exception as e:
        print(f'    [WARN] not OLE/HWP: {e}')
        return ''
    # 압축 플래그 (FileHeader byte 36 bit0)
    fh = ole.openstream('FileHeader').read()
    compressed = bool(fh[36] & 0x01) if len(fh) > 36 else True
    out_parts: list[str] = []
    sections = []
    for s in ole.listdir():
        joined = '/'.join(s)
        if joined.startswith('BodyText/Section'):
            sections.append(s)
    # 섹션 번호 순 정렬
    sections.sort(key=lambda s: int(re.search(r'\d+', s[-1]).group(0)))
    for s in sections:
        data = ole.openstream(s).read()
        if compressed:
            try:
                data = zlib.decompress(data, -15)
            except Exception as e:
                print(f'    [WARN] decompress fail {s}: {e}')
                continue
        # 레코드 파싱
        pos = 0
        while pos + 4 <= len(data):
            h = struct.unpack('<I', data[pos:pos + 4])[0]
            pos += 4
            tag = h & 0x3FF
            size = (h >> 20) & 0xFFF
            if size == 0xFFF:
                size = struct.unpack('<I', data[pos:pos + 4])[0]
                pos += 4
            body = data[pos:pos + size]
            pos += size
            # 67 = HWPTAG_PARA_TEXT
            if tag == 67 and body:
                try:
                    s_ = body.decode('utf-16-le', errors='replace')
                    # 제어문자 정리(0x00~0x1F) – 줄바꿈만 보존
                    s_ = ''.join(ch if (ord(ch) >= 0x20 or ch in '\n\t') else ' ' for ch in s_)
                    out_parts.append(s_)
                except Exception:
                    pass
    text = '\n'.join(p.strip() for p in out_parts if p and p.strip())
    # 자잘한 노이즈 (HWP 내부 식별자 같은 토큰) 정리
    text = re.sub(r'^[a-zA-Z]{4,8}\s+$', '', text, flags=re.MULTILINE)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


# ---------------- 학칙 수집 ----------------

RULE_LIST_URL = 'https://plus.cnu.ac.kr/_prog/rule/?site_dvs_cd=kr&menu_dvs_cd=06050101&gubun={gubun}'
RULE_VIEW_URL = 'https://plus.cnu.ac.kr/_prog/rule/view_pop.php?mng_no={mng_no}'
RULE_DOWNLOAD_BASE = 'https://plus.cnu.ac.kr/_prog/rule/'

def parse_rule_list(gubun: int) -> list[dict]:
    """gubun(편) 리스트 페이지에서 각 규정 메타 추출. tbody 내 각 <tr> 의 td 들을 파싱."""
    html = fetch_utf8(RULE_LIST_URL.format(gubun=gubun))
    if not html:
        return []
    m = re.search(r'<tbody[^>]*>(.*?)</tbody>', html, re.S)
    if not m:
        return []
    tb = m.group(1)
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', tb, re.S)
    items: list[dict] = []
    for row in rows:
        tds = re.findall(r'<td[^>]*>(.*?)</td>', row, re.S)
        if len(tds) < 5:
            continue
        # td0=번호, td1=편, td2=장(빈경우 있음), td3=규정명(앵커), td4=관리부서
        mng_m = re.search(r'mng_no=(\d+)', tds[3])
        name_m = re.search(r'>([^<]+)</a>', tds[3])
        if not mng_m or not name_m:
            continue
        items.append({
            'mng_no': mng_m.group(1),
            'rule_name': re.sub(r'\s+', ' ', name_m.group(1)).strip(),
            'book': re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', tds[1])).strip(),
            'chapter': re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', tds[2])).strip(),
        })
    return items


ATTACH_RE = re.compile(r'href=[\"\']?(download\.php\?atch_path=[^\"\'> ]+\.hwp[^\"\'> ]*)', re.I)
HTML_TAG_RE = re.compile(r'<[^>]+>')
SCRIPT_RE = re.compile(r'<(?:script|style)[^>]*>.*?</(?:script|style)>', re.S | re.I)


def html_to_plain(html: str) -> str:
    s = SCRIPT_RE.sub(' ', html)
    s = HTML_TAG_RE.sub(' ', s)
    s = (
        s.replace('&nbsp;', ' ')
        .replace('&amp;', '&')
        .replace('&lt;', '<')
        .replace('&gt;', '>')
        .replace('&quot;', '"')
        .replace('&#39;', "'")
    )
    s = re.sub(r'[ \t]+', ' ', s)
    s = re.sub(r'\s*\n\s*', '\n', s)
    s = re.sub(r'\n{3,}', '\n\n', s)
    return s.strip()


def fetch_rule_doc(meta: dict) -> dict | None:
    """규정 view_pop + HWP 본문 -> 문서 1건."""
    mng_no = meta['mng_no']
    rule_name = meta['rule_name']
    view_url = RULE_VIEW_URL.format(mng_no=mng_no)
    html = fetch_utf8(view_url)
    if not html:
        return None
    # HWP attachment URL
    m = ATTACH_RE.search(html)
    hwp_text = ''
    hwp_url = None
    if m:
        atch = m.group(1).replace('&amp;', '&')
        hwp_url = urljoin(RULE_DOWNLOAD_BASE, atch)
        hwp_bytes = safe_get(hwp_url, timeout=40)
        if hwp_bytes and hwp_bytes[:4] == b'\xd0\xcf\x11\xe0':
            hwp_text = hwp_extract_text(hwp_bytes)
    view_plain = html_to_plain(html)
    # 합성 본문: 메타 + HWP 본문
    parts = [
        f'규정명: {rule_name}',
        f'분류: {meta["book"]} / {meta["chapter"]}',
        f'관리: 충남대학교 학칙규정 (mng_no={mng_no})',
    ]
    if hwp_text:
        parts.append('')
        parts.append('[규정 전문]')
        parts.append(hwp_text)
    else:
        # HWP 실패시 HTML view 의 plain text 사용 (개정이력/요약)
        parts.append('')
        parts.append('[규정 요약 / 개정이력]')
        parts.append(view_plain)
    text = '\n'.join(parts)
    return {
        'doc': make_doc(view_url, rule_name, text, 'B_academic'),
        'meta': {'mng_no': mng_no, 'hwp_url': hwp_url, 'hwp_len': len(hwp_text), 'view_len': len(view_plain)},
    }


def collect_rules() -> tuple[list[dict], list[dict]]:
    """모든 8 편의 규정 메타 수집 후 본문 다운로드."""
    print('[1/2] 학칙규정 수집 시작')
    all_metas: list[dict] = []
    for gubun in range(1, 9):
        metas = parse_rule_list(gubun)
        print(f'  gubun={gubun}: {len(metas)}건')
        all_metas.extend(metas)
    # 동일 mng_no 중복 제거
    seen = set()
    uniq = []
    for m in all_metas:
        if m['mng_no'] in seen:
            continue
        seen.add(m['mng_no'])
        uniq.append(m)
    print(f'  총 규정 수(중복제거): {len(uniq)}')
    docs: list[dict] = []
    rule_report: list[dict] = []
    for i, m in enumerate(uniq, 1):
        print(f'  [{i}/{len(uniq)}] {m["rule_name"][:40]} (mng={m["mng_no"]})')
        out = fetch_rule_doc(m)
        if out is None:
            rule_report.append({'mng_no': m['mng_no'], 'rule_name': m['rule_name'], 'status': 'fetch_fail'})
            continue
        d = out['doc']
        if len(d['content']) < 200:
            rule_report.append({'mng_no': m['mng_no'], 'rule_name': m['rule_name'], 'status': 'too_short', 'len': len(d['content'])})
            continue
        docs.append(d)
        rule_report.append({'mng_no': m['mng_no'], 'rule_name': m['rule_name'], 'status': 'ok', **out['meta'], 'content_len': len(d['content'])})
        time.sleep(0.2)
    return docs, rule_report


# ---------------- 입학처 수집 ----------------

IPSI_SEEDS = [
    'https://ipsi.cnu.ac.kr/html/uadm/',
    'https://ipsi.cnu.ac.kr/html/gadm/',
]
IPSI_HOST_PREFIX = 'https://ipsi.cnu.ac.kr/html/'


def discover_ipsi_urls() -> list[str]:
    """학부/대학원 입학처 페이지 BFS(2단계)."""
    discovered: set[str] = set()
    frontier = set()
    for seed in IPSI_SEEDS:
        html = fetch_utf8(seed)
        if not html:
            continue
        hrefs = re.findall(r'href=[\"\']([^\"\'#?]+\.html)[\"\']', html)
        for h in hrefs:
            full = urljoin(seed, h)
            if full.startswith(IPSI_HOST_PREFIX):
                discovered.add(full)
                frontier.add(full)
    # 1단계 deepen
    new_found = set()
    for u in list(frontier)[:50]:
        html = fetch_utf8(u)
        if not html:
            continue
        hrefs = re.findall(r'href=[\"\']([^\"\'#?]+\.html)[\"\']', html)
        for h in hrefs:
            full = urljoin(u, h)
            if full.startswith(IPSI_HOST_PREFIX) and full not in discovered:
                new_found.add(full)
    discovered |= new_found
    return sorted(discovered)


def collect_ipsi(urls: list[str]) -> tuple[list[dict], list[dict]]:
    print('[2/2] 입학처 수집 시작')
    docs: list[dict] = []
    rep: list[dict] = []
    for i, u in enumerate(urls, 1):
        html = fetch_utf8(u)
        if not html:
            rep.append({'url': u, 'status': 'fetch_fail'})
            continue
        # title from <title>
        tm = re.search(r'<title[^>]*>([^<]+)</title>', html)
        title = tm.group(1).strip() if tm else u
        # trafilatura
        body = extract_main_text(html, min_len=80)
        if not body:
            # fallback: html_to_plain
            plain = html_to_plain(html)
            if len(plain) < 200:
                rep.append({'url': u, 'status': 'no_body'})
                continue
            body = plain
        if len(body) < 120:
            rep.append({'url': u, 'status': 'too_short', 'len': len(body)})
            continue
        d = make_doc(u, title, body, 'C_administration')
        docs.append(d)
        rep.append({'url': u, 'status': 'ok', 'len': len(d['content'])})
        print(f'  [{i}/{len(urls)}] OK {len(d["content"])}b - {title[:40]}')
        time.sleep(0.15)
    return docs, rep


# ---------------- main ----------------

def main():
    rules, rule_rep = collect_rules()
    ipsi_urls = discover_ipsi_urls()
    print(f'  입학처 후보 URL: {len(ipsi_urls)}건')
    ipsi_docs, ipsi_rep = collect_ipsi(ipsi_urls)

    all_docs = rules + ipsi_docs
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(all_docs, f, ensure_ascii=False, indent=2)

    # 리포트
    report_path = OUT_PATH.with_name('regulations_admission.report.json')
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump({
            'rules': rule_rep,
            'ipsi': ipsi_rep,
            'totals': {
                'rules_docs': len(rules),
                'ipsi_docs': len(ipsi_docs),
                'all_docs': len(all_docs),
            },
        }, f, ensure_ascii=False, indent=2)

    print('=' * 60)
    print(f'학칙규정 수집: {len(rules)}건')
    print(f'입학처(ipsi) 수집: {len(ipsi_docs)}건')
    print(f'총 문서: {len(all_docs)}건')
    print(f'저장: {OUT_PATH}')
    print(f'리포트: {report_path}')


if __name__ == '__main__':
    main()
