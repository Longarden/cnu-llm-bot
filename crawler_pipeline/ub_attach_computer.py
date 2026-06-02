# -*- coding: utf-8 -*-
"""
computer.cnu.ac.kr 첨부 추출 워커 (build-only).
- 보드: notice / bachelor / job / project
- 상세: ?mode=view&articleNo=NNN
- 첨부 다운로드: ?mode=download2&articleNo=NNN&attachNo=NNN
- PDF -> pdfplumber(실패시 PyPDF2)
- HWP/HWPX -> olefile / zipfile best-effort
- 이미지 -> data/attachments_img/computer 에 다운로드만
출력: data/crawled_staging/ub_attach_computer.json (텍스트 레코드)
"""
import os, re, io, json, zlib, struct, time, zipfile, datetime, traceback
import requests
from bs4 import BeautifulSoup

ROOT = r"C:/Users/dmsak/cnu-llm-bot"
OUT_JSON = os.path.join(ROOT, "data", "crawled_staging", "ub_attach_computer.json")
IMG_DIR = os.path.join(ROOT, "data", "attachments_img", "computer")
os.makedirs(IMG_DIR, exist_ok=True)
os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
SITE = "https://computer.cnu.ac.kr/computer/notice/{board}.do"

# board -> data_category. 학사/졸업/교과 관련은 F_department, 공지/취업은 K_notices
BOARDS = {
    "notice":   "K_notices",
    "bachelor": "F_department",
    "job":      "K_notices",
    "project":  "F_department",
}
MAX_PER_BOARD = 15  # 최근 게시글 상한
IMG_EXT = (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp")
PDF_EXT = (".pdf",)
HWP_EXT = (".hwp", ".hwpx")

REPLACEMENT = "�"


def fetch(url, binary=False, retries=3, timeout=60):
    last = None
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=H, timeout=(15, timeout))
            r.raise_for_status()
            if binary:
                return r.content, r.headers
            return r.content.decode("utf-8", "replace"), r.headers
        except Exception as e:
            last = e
            time.sleep(2 * (attempt + 1))
    raise last


def clean_text(t):
    if not t:
        return ""
    t = t.replace("\x00", " ")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def list_articles(board):
    url = SITE.format(board=board)
    html, _ = fetch(url)
    s = BeautifulSoup(html, "html.parser")
    arts = []
    for a in s.find_all("a", href=True):
        m = re.search(r"articleNo=(\d+)", a["href"])
        if m:
            arts.append(m.group(1))
    # 순서 유지 중복 제거
    seen, ordered = set(), []
    for a in arts:
        if a not in seen:
            seen.add(a); ordered.append(a)
    return ordered[:MAX_PER_BOARD]


def parse_detail(board, article_no):
    url = SITE.format(board=board) + f"?mode=view&articleNo={article_no}"
    html, _ = fetch(url)
    s = BeautifulSoup(html, "html.parser")
    # 제목: <caption>에 실제 게시글 제목이 들어있음(CNU 게시판 공통)
    title = ""
    cap = s.find("caption")
    if cap:
        ct = cap.get_text(" ", strip=True)
        if ct and len(ct) > 4 and "일반소식" not in ct[:8]:
            title = ct
    if not title:
        for sel in ["h3", "h4", ".view_title", ".board_view .title", "td.title"]:
            el = s.select_one(sel)
            if el and el.get_text(strip=True):
                title = el.get_text(strip=True); break
    if not title:
        t = s.find("title")
        if t:
            raw = t.get_text(" ", strip=True)
            # "공지사항 > ... ( 실제제목 ) | 컴퓨터..." 형태에서 괄호 안 추출 시도
            mm = re.search(r"\(\s*(.+?)\s*\)\s*\|", raw)
            title = mm.group(1) if mm else raw.split("|")[0].strip()
    # 본문 텍스트
    body_el = None
    for sel in [".board_view", ".view_con", ".bbs_content", "#con", ".content", ".view"]:
        body_el = s.select_one(sel)
        if body_el:
            break
    body_text = body_el.get_text("\n", strip=True) if body_el else ""
    # 첨부 링크
    attaches = []
    for a in s.find_all("a", href=True):
        hr = a["href"]
        if "mode=download2" in hr and "attachNo=" in hr:
            fn = a.get_text(strip=True)
            if hr.startswith("?"):
                full = SITE.format(board=board) + hr
            elif hr.startswith("http"):
                full = hr
            else:
                full = "https://computer.cnu.ac.kr" + hr
            attaches.append({"name": fn, "url": full})
    # 중복 제거(attachNo 기준)
    seen, uniq = set(), []
    for at in attaches:
        m = re.search(r"attachNo=(\d+)", at["url"])
        key = m.group(1) if m else at["url"]
        if key not in seen:
            seen.add(key); uniq.append(at)
    return url, clean_text(title), clean_text(body_text), uniq


def ext_of(name, headers=None):
    name = name or ""
    m = re.search(r"\.([A-Za-z0-9]{1,5})(?:$|\?)", name)
    if m:
        return "." + m.group(1).lower()
    if headers:
        cd = headers.get("Content-Disposition", "")
        m2 = re.search(r"filename\*?=.*?\.([A-Za-z0-9]{1,5})", cd)
        if m2:
            return "." + m2.group(1).lower()
    return ""


# ---------- 파서 ----------
def extract_pdf(data):
    txt = ""
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            parts = []
            for pg in pdf.pages[:30]:
                parts.append(pg.extract_text() or "")
            txt = "\n".join(parts)
    except Exception:
        txt = ""
    if len(txt.strip()) < 10:
        try:
            import PyPDF2
            rd = PyPDF2.PdfReader(io.BytesIO(data))
            parts = [(p.extract_text() or "") for p in rd.pages[:30]]
            txt = "\n".join(parts)
        except Exception:
            pass
    return clean_text(txt)


def extract_hwp(data):
    """olefile best-effort: BodyText/Section* 스트림 zlib 해제 후 UTF-16LE 텍스트."""
    import olefile
    try:
        if not olefile.isOleFile(io.BytesIO(data)):
            return ""
        ole = olefile.OleFileIO(io.BytesIO(data))
        # 압축 여부: FileHeader 스트림 36바이트 플래그
        compressed = True
        try:
            if ole.exists("FileHeader"):
                fh = ole.openstream("FileHeader").read()
                compressed = bool(fh[36] & 1)
        except Exception:
            pass
        sections = []
        for entry in ole.listdir():
            if len(entry) > 1 and entry[0] == "BodyText" and entry[1].lower().startswith("section"):
                sections.append(entry)
        sections.sort(key=lambda e: e[1])
        out = []
        for sec in sections:
            raw = ole.openstream(sec).read()
            if compressed:
                try:
                    raw = zlib.decompress(raw, -15)
                except Exception:
                    pass
            out.append(_hwp_records_to_text(raw))
        ole.close()
        return clean_text("\n".join(out))
    except Exception:
        return ""


def _hwp_records_to_text(buf):
    """HWP5 레코드 파싱: tag_id==67(PARA_TEXT)인 UTF-16LE 텍스트만 추출."""
    texts = []
    i, n = 0, len(buf)
    try:
        while i + 4 <= n:
            header = struct.unpack_from("<I", buf, i)[0]
            tag_id = header & 0x3FF
            size = (header >> 20) & 0xFFF
            i += 4
            if size == 0xFFF:
                if i + 4 > n:
                    break
                size = struct.unpack_from("<I", buf, i)[0]
                i += 4
            payload = buf[i:i + size]
            i += size
            if tag_id == 67:  # HWPTAG_PARA_TEXT
                s = payload.decode("utf-16le", "ignore")
                # 제어문자 제거
                s = "".join(ch for ch in s if ch == "\n" or ord(ch) >= 32)
                if s.strip():
                    texts.append(s)
    except Exception:
        pass
    return "\n".join(texts)


def extract_hwpx(data):
    """HWPX = zip, Contents/section*.xml 의 텍스트."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
        parts = []
        for nm in zf.namelist():
            if nm.lower().endswith(".xml") and "section" in nm.lower():
                xml = zf.read(nm).decode("utf-8", "ignore")
                soup = BeautifulSoup(xml, "html.parser")
                parts.append(soup.get_text(" ", strip=True))
        return clean_text("\n".join(parts))
    except Exception:
        return ""


# ---------- 메인 ----------
def main():
    now = datetime.datetime.now()
    last_crawled = now.isoformat()
    valid_until = (now + datetime.timedelta(days=30)).isoformat()

    records = []
    img_downloads = []
    stats = {"pdf": 0, "hwp": 0, "hwpx": 0, "img": 0, "other": 0, "fail": 0}
    fail_log = []

    for board, category in BOARDS.items():
        try:
            arts = list_articles(board)
        except Exception as e:
            fail_log.append(f"list {board}: {e}")
            continue
        for ano in arts:
            try:
                src_url, title, body, attaches = parse_detail(board, ano)
            except Exception as e:
                fail_log.append(f"detail {board}/{ano}: {e}")
                continue
            if not attaches:
                continue
            for at in attaches:
                name = at["name"]
                url = at["url"]
                try:
                    content, hdrs = fetch(url, binary=True)
                except Exception as e:
                    stats["fail"] += 1
                    fail_log.append(f"dl {board}/{ano} {name}: {e}")
                    continue
                ext = ext_of(name, hdrs)
                attach_text = ""
                kind = "other"
                if ext in IMG_EXT:
                    kind = "img"
                    safe = re.sub(r"[^\w.\-]", "_", f"{board}_{ano}_{name}") or f"{board}_{ano}{ext}"
                    if not safe.lower().endswith(ext):
                        safe += ext
                    path = os.path.join(IMG_DIR, safe)
                    with open(path, "wb") as f:
                        f.write(content)
                    img_downloads.append({"board": board, "article": ano,
                                          "src_url": src_url, "name": name,
                                          "path": path.replace("\\", "/")})
                    stats["img"] += 1
                    continue
                elif ext in PDF_EXT:
                    kind = "pdf"; attach_text = extract_pdf(content)
                elif ext == ".hwp":
                    kind = "hwp"; attach_text = extract_hwp(content)
                elif ext == ".hwpx":
                    kind = "hwpx"; attach_text = extract_hwpx(content)
                else:
                    kind = "other"
                    fail_log.append(f"skip ext {ext} {board}/{ano} {name}")

                stats[kind] = stats.get(kind, 0) + 1

                # original_text 구성: 제목 + 첨부파일명 + (본문) + 추출텍스트
                pieces = [p for p in [title, body, f"[첨부] {name}", attach_text] if p]
                original_text = clean_text("\n".join(pieces))
                content_field = attach_text if attach_text else clean_text(
                    "\n".join([p for p in [title, body, f"[첨부] {name}", url] if p]))

                if len(original_text) < 30:
                    # 추출 실패/짧음: 제목+첨부명+링크로 최소 레코드 보강
                    original_text = clean_text(
                        f"{title}\n[첨부파일] {name}\n[원글] {src_url}\n[다운로드] {url}\n{body}")
                if len(original_text) < 30:
                    stats["fail"] += 1
                    fail_log.append(f"too_short {board}/{ano} {name}")
                    continue

                records.append({
                    "source_url": src_url,
                    "data_category": category,
                    "last_crawled_at": last_crawled,
                    "valid_until": valid_until,
                    "freshness_tier": "time_sensitive",
                    "original_text": original_text,
                    "title": title or name,
                    "content": content_field,
                    "date": now.strftime("%Y-%m-%d"),
                })
                time.sleep(0.2)

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    # 이미지 목록 리포트
    img_report = os.path.join(IMG_DIR, "_img_manifest.json")
    with open(img_report, "w", encoding="utf-8") as f:
        json.dump(img_downloads, f, ensure_ascii=False, indent=2)

    # 콘솔 보고 (UTF-8 파일로도 남겨 모지바케 방지)
    rep = {
        "text_records": len(records),
        "stats": stats,
        "img_downloads": len(img_downloads),
        "samples": [{"title": r["title"], "extract": r["content"][:200]}
                    for r in records[:3]],
        "img_paths": [d["path"] for d in img_downloads],
        "fail_log": fail_log[:30],
    }
    with open(os.path.join(ROOT, "_ub_attach_computer_report.json"), "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    print(json.dumps(rep, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
