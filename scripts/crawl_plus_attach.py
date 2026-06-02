# -*- coding: utf-8 -*-
"""plus.cnu.ac.kr attachment extraction worker.

Boards:
  sub07_0701  학사공지 (academic notices)
  sub07_0702  일반/장학공지 (general / scholarship notices)

For each recent post:
  - open detail page (?mode=V&no=...)
  - capture title + inline body text
  - find attachment links: common/download.php?... , /Upl/... , direct .pdf/.hwp/.hwpx/img
  - PDF -> pdfplumber (fallback PyPDF2) text
  - HWP/HWPX -> olefile / zip best-effort text
  - images (.jpg/.png/.gif) -> download only into data/attachments_img/plus/
Outputs:
  data/crawled_staging/ub_attach_plus.json  (text records, 9-key schema)
  data/attachments_img/plus/                (downloaded images)
"""
import os, re, io, sys, json, time, zlib, zipfile, datetime, tempfile
import requests
from urllib.parse import urljoin, urlparse, parse_qs, unquote
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding="utf-8")

ROOT = "C:/Users/dmsak/cnu-llm-bot"
OUT_JSON = os.path.join(ROOT, "data", "crawled_staging", "ub_attach_plus.json")
IMG_DIR = os.path.join(ROOT, "data", "attachments_img", "plus")
os.makedirs(IMG_DIR, exist_ok=True)
os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)

BASE = "https://plus.cnu.ac.kr"
BOARD = BASE + "/_prog/_board/"
HDR = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

# board code -> (menu, default data_category)
BOARDS = [
    ("sub07_0701", "0701", "B_academic"),   # 학사공지
    ("sub07_0702", "0702", "K_notices"),    # 일반/장학공지
]
MAX_POSTS_PER_BOARD = 20

IMG_EXT = (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp")
PDF_EXT = (".pdf",)
HWP_EXT = (".hwp", ".hwpx")

# category hints
ACAD_KW = ["학사일정", "졸업", "수강신청", "휴학", "복학", "전공", "학점", "성적", "등록",
           "학위", "교과", "재학", "수료", "이수", "학적"]
SCHOL_KW = ["장학", "장학금", "학자금"]

session = requests.Session()
session.headers.update(HDR)


def fetch(url, **kw):
    for attempt in range(3):
        try:
            r = session.get(url, timeout=30, **kw)
            return r
        except Exception as e:
            if attempt == 2:
                raise
            time.sleep(1.5)
    return None


def decode_cd_filename(cd):
    if not cd:
        return None
    m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^"\;]+)"?', cd)
    if not m:
        return None
    raw = m.group(1).strip()
    # server sends latin-1-mangled UTF-8 (mojibake) — fix it
    for enc in ("utf-8",):
        try:
            fixed = raw.encode("latin-1").decode(enc)
            return unquote(fixed)
        except Exception:
            pass
    return unquote(raw)


def clean_text(t):
    if not t:
        return ""
    t = re.sub(r"[ \t ]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


# ---------- list ----------
def list_posts(code, menu):
    url = f"{BOARD}?code={code}&site_dvs_cd=kr&menu_dvs_cd={menu}"
    r = fetch(url)
    r.encoding = "utf-8"
    s = BeautifulSoup(r.text, "html.parser")
    posts = []
    seen = set()
    for a in s.select("a[href]"):
        h = a.get("href") or ""
        if "mode=V" not in h and "mode=view" not in h:
            continue
        m = re.search(r"no=(\d+)", h)
        if not m:
            continue
        no = m.group(1)
        if no in seen:
            continue
        seen.add(no)
        title = a.get_text(strip=True)
        full = urljoin(url + "&", h.lstrip("./"))
        # rebuild canonical detail url
        detail = f"{BOARD}?mode=V&no={no}&code={code}&site_dvs_cd=kr&menu_dvs_cd={menu}"
        posts.append({"no": no, "title": title, "url": detail})
    return posts[:MAX_POSTS_PER_BOARD]


# ---------- detail ----------
def parse_detail(post):
    r = fetch(post["url"])
    r.encoding = "utf-8"
    s = BeautifulSoup(r.text, "html.parser")

    title = post["title"]
    el = s.select_one(".board_viewTit")
    if el and el.get_text(strip=True):
        title = el.get_text(strip=True)

    body = ""
    bel = s.select_one(".board_viewDetail")
    if bel:
        body = clean_text(bel.get_text("\n", strip=True))

    date = ""
    info = s.select_one(".board_viewInfo")
    if info:
        dm = re.search(r"(20\d{2}[.\-/]\s?\d{1,2}[.\-/]\s?\d{1,2})", info.get_text(" "))
        if dm:
            date = dm.group(1).replace(" ", "")

    # attachments: ONLY within the real attachment box (.file) + inline body files.
    # The /Upl/ links elsewhere are site-wide footer/menu boilerplate -> ignore.
    atts = []
    seen_urls = set()
    scopes = s.select(".file") + s.select(".board_viewDetail")
    for scope in scopes:
        for a in scope.select("a[href]"):
            h = a.get("href") or ""
            low = h.lower()
            is_dl = ("download.php" in low or "download.do" in low or "filedown" in low)
            is_file = low.split("?")[0].endswith(PDF_EXT + HWP_EXT + IMG_EXT)
            if not (is_dl or is_file):
                continue
            full = urljoin(post["url"], h)
            if full in seen_urls:
                continue
            seen_urls.add(full)
            atts.append({"label": a.get_text(strip=True), "url": full})
    return title, body, date, atts


# ---------- attachment download ----------
def download(att, referer):
    r = fetch(att["url"], headers={**HDR, "Referer": referer}, stream=True)
    if r.status_code != 200:
        return None, None, None
    data = r.content
    fname = decode_cd_filename(r.headers.get("Content-Disposition"))
    if not fname:
        path = urlparse(att["url"]).path
        fname = unquote(os.path.basename(path)) or att.get("label") or "file"
    ctype = (r.headers.get("Content-Type") or "").lower()
    return data, fname, ctype


def kind_of(fname, ctype, label):
    base = (fname or "").lower()
    lab = (label or "").lower()
    if base.endswith(IMG_EXT) or "image/" in ctype:
        return "img"
    if base.endswith(PDF_EXT) or "pdf" in ctype:
        return "pdf"
    if base.endswith(HWP_EXT) or lab.endswith(HWP_EXT):
        return "hwp"
    if base.endswith(".zip"):
        return "zip"
    return "other"


# ---------- PDF ----------
def extract_pdf(data):
    try:
        import pdfplumber
        out = []
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for pg in pdf.pages[:30]:
                t = pg.extract_text() or ""
                if t:
                    out.append(t)
        txt = "\n".join(out)
        if txt.strip():
            return clean_text(txt)
    except Exception:
        pass
    try:
        import PyPDF2
        rd = PyPDF2.PdfReader(io.BytesIO(data))
        out = [(p.extract_text() or "") for p in rd.pages[:30]]
        return clean_text("\n".join(out))
    except Exception:
        return ""


# ---------- HWP (olefile best-effort) ----------
def extract_hwp(data):
    # HWPX = zip container with XML
    if data[:2] == b"PK":
        try:
            zf = zipfile.ZipFile(io.BytesIO(data))
            texts = []
            for n in zf.namelist():
                if n.startswith("Contents/") and n.endswith(".xml"):
                    raw = zf.read(n).decode("utf-8", "ignore")
                    raw = re.sub(r"<[^>]+>", " ", raw)
                    texts.append(raw)
            return clean_text(" ".join(texts))
        except Exception:
            return ""
    # classic HWP = OLE compound, BodyText/Section* streams (zlib raw deflate)
    try:
        import olefile
        ole = olefile.OleFileIO(io.BytesIO(data))
        chunks = []
        compressed = True
        if ole.exists("FileHeader"):
            fh = ole.openstream("FileHeader").read()
            # byte 36 bit0 -> compressed flag
            if len(fh) > 36:
                compressed = bool(fh[36] & 1)
        for entry in ole.listdir():
            if entry and entry[0] == "BodyText":
                raw = ole.openstream(entry).read()
                if compressed:
                    try:
                        raw = zlib.decompress(raw, -15)
                    except Exception:
                        continue
                # HWP body is record-structured; text runs are UTF-16LE inside
                # PARA_TEXT records (tag 67). Walk records and pull only those.
                txt = _hwp_walk_records(raw)
                if txt:
                    chunks.append(txt)
        ole.close()
        cand = clean_text(" ".join(chunks))
        # validity gate: reject mojibake. Require enough Hangul/ASCII ratio.
        if not cand:
            return ""
        good = sum(1 for ch in cand if ("가" <= ch <= "힣") or ch.isascii())
        if len(cand) >= 20 and good / max(1, len(cand)) >= 0.85:
            return cand
        return ""
    except Exception:
        return ""


def _hwp_walk_records(buf):
    """Parse HWP5 BodyText record stream; extract PARA_TEXT (tag 67) UTF-16LE."""
    out = []
    i, n = 0, len(buf)
    while i + 4 <= n:
        header = int.from_bytes(buf[i:i + 4], "little")
        tag = header & 0x3FF
        size = (header >> 20) & 0xFFF
        i += 4
        if size == 0xFFF:  # extended size
            if i + 4 > n:
                break
            size = int.from_bytes(buf[i:i + 4], "little")
            i += 4
        data = buf[i:i + size]
        i += size
        if tag == 67:  # HWPTAG_PARA_TEXT
            try:
                s = data.decode("utf-16-le", "ignore")
            except Exception:
                continue
            # strip HWP inline control chars (code points < 32 used as markers)
            s = "".join(ch for ch in s if ch == "\n" or ch == "\t" or ord(ch) >= 32)
            # drop CJK-ideograph / kana runs: these boards are Hangul+ASCII only,
            # so any CJK ideograph here is mis-decoded binary, not real content.
            s = "".join(ch for ch in s
                        if not ("　" <= ch <= "〿"      # CJK punct/space
                                or "぀" <= ch <= "ヿ"   # kana
                                or "㐀" <= ch <= "鿿"   # CJK ideographs
                                or "豈" <= ch <= "﫿")) # CJK compat
            out.append(s)
    return " ".join(out).strip()


def pick_category(default_cat, title, body):
    txt = (title or "") + " " + (body or "")
    if any(k in txt for k in ACAD_KW):
        return "B_academic"
    if any(k in txt for k in SCHOL_KW):
        return "K_notices"
    return default_cat


def main():
    now = datetime.datetime.now()
    last_crawled = now.isoformat()
    valid_until = (now + datetime.timedelta(days=7)).isoformat()

    records = []
    img_paths = []
    stats = {"posts": 0, "pdf": 0, "hwp": 0, "img": 0, "zip": 0, "other": 0,
             "pdf_fail": 0, "hwp_fail": 0}
    img_report = []

    for code, menu, default_cat in BOARDS:
        try:
            posts = list_posts(code, menu)
        except Exception as e:
            print(f"[LIST FAIL] {code}: {e}")
            continue
        print(f"[{code}] {len(posts)} posts")
        for post in posts:
            stats["posts"] += 1
            try:
                title, body, date, atts = parse_detail(post)
            except Exception as e:
                print(f"  [DETAIL FAIL] no={post['no']} {e}")
                continue

            attach_texts = []
            attach_names = []
            for att in atts:
                try:
                    data, fname, ctype = download(att, post["url"])
                except Exception as e:
                    print(f"  [DL FAIL] {att['url'][:70]} {e}")
                    continue
                if not data:
                    continue
                kind = kind_of(fname, ctype, att.get("label"))
                attach_names.append(fname)
                if kind == "img":
                    stats["img"] += 1
                    safe = re.sub(r"[^0-9A-Za-z._\-가-힣]", "_", fname) or "img"
                    dest = os.path.join(IMG_DIR, f"{post['no']}_{safe}")
                    if not os.path.splitext(dest)[1]:
                        dest += ".jpg"
                    try:
                        with open(dest, "wb") as f:
                            f.write(data)
                        img_paths.append(dest.replace("\\", "/"))
                        img_report.append({
                            "board": code, "post_no": post["no"],
                            "title": title, "filename": fname,
                            "path": dest.replace("\\", "/"),
                            "source_url": att["url"],
                        })
                    except Exception as e:
                        print(f"  [IMG SAVE FAIL] {e}")
                elif kind == "pdf":
                    stats["pdf"] += 1
                    t = extract_pdf(data)
                    if t and len(t) > 10:
                        attach_texts.append(f"[첨부:{fname}]\n{t}")
                    else:
                        stats["pdf_fail"] += 1
                elif kind == "hwp":
                    stats["hwp"] += 1
                    t = extract_hwp(data)
                    if t and len(t) > 10:
                        attach_texts.append(f"[첨부:{fname}]\n{t}")
                    else:
                        stats["hwp_fail"] += 1
                elif kind == "zip":
                    stats["zip"] += 1
                else:
                    stats["other"] += 1
                time.sleep(0.2)

            combined = "\n\n".join([p for p in [body] + attach_texts if p]).strip()
            # original_text = title + body/attachment text
            original_text = (title + "\n" + combined).strip()
            if attach_names and len(original_text) < 30:
                original_text = (title + "\n첨부파일: " + ", ".join(attach_names)).strip()
            if len(original_text) < 30:
                # honest skip: nothing meaningful extracted
                print(f"  [SKIP <30] no={post['no']} title={title[:30]}")
                continue

            cat = pick_category(default_cat, title, combined)
            rec = {
                "source_url": post["url"],
                "data_category": cat,
                "last_crawled_at": last_crawled,
                "valid_until": valid_until,
                "freshness_tier": "time_sensitive",
                "original_text": original_text,
                "title": title,
                "content": combined if combined else ("첨부파일: " + ", ".join(attach_names)),
                "date": date,
            }
            records.append(rec)
            time.sleep(0.25)

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    rep_path = os.path.join(IMG_DIR, "_image_report.json")
    with open(rep_path, "w", encoding="utf-8") as f:
        json.dump(img_report, f, ensure_ascii=False, indent=2)

    print("\n==== RESULT ====")
    print("text records:", len(records))
    print("stats:", json.dumps(stats, ensure_ascii=False))
    print("images downloaded:", len(img_paths))
    for p in img_paths:
        print("  IMG:", p)
    print("\n---- samples ----")
    for rec in records[:3]:
        print("TITLE:", rec["title"])
        print("CAT:", rec["data_category"], "DATE:", rec["date"])
        print("ORIG[:300]:", rec["original_text"][:300].replace("\n", " "))
        print("-")


if __name__ == "__main__":
    main()
