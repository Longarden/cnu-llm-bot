"""게시판 첨부파일(HWP/PDF) 텍스트 추출 helper.

- HWP 5.x: olefile + zlib + HWPTAG_PARA_TEXT(tag=67) (pyhwp 의존 X)
- PDF    : pdfplumber 우선, 실패시 PyPDF2 폴백
- 다운로드: requests, retry, 사이즈 상한, content magic 검증

게시판 view 페이지의 첨부 링크를 찾아 다운로드 -> 텍스트 합쳐 반환.
"""
from __future__ import annotations

import re
import struct
import time
import zlib
from io import BytesIO
from typing import Optional
from urllib.parse import urljoin

import requests

_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
MAX_BYTES = 20 * 1024 * 1024  # 첨부당 20MB 상한 (T4 메모리/시간 안전망)


def safe_download(url: str, timeout: int = 40, retries: int = 1) -> Optional[bytes]:
    """첨부 url -> bytes. 실패시 None. 사이즈 상한 적용."""
    last = None
    for _ in range(retries + 1):
        try:
            r = requests.get(url, headers=_HEADERS, timeout=timeout, stream=True)
            if r.status_code != 200:
                last = f"status={r.status_code}"
                continue
            data = b""
            for chunk in r.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    break
                data += chunk
                if len(data) > MAX_BYTES:
                    last = f"too large > {MAX_BYTES}"
                    return None
            return data if data else None
        except Exception as e:
            last = str(e)
            time.sleep(0.5)
    return None


# ---------------- HWP ----------------

def hwp_extract_text(hwp_bytes: bytes) -> str:
    """HWP 5.x OLE compound -> text. BodyText/SectionN -> HWPTAG_PARA_TEXT."""
    if not hwp_bytes or hwp_bytes[:4] != b"\xd0\xcf\x11\xe0":
        return ""
    try:
        import olefile
    except Exception:
        return ""
    try:
        ole = olefile.OleFileIO(BytesIO(hwp_bytes))
    except Exception:
        return ""
    try:
        fh = ole.openstream("FileHeader").read()
    except Exception:
        return ""
    compressed = bool(fh[36] & 0x01) if len(fh) > 36 else True
    sections = []
    for s in ole.listdir():
        if "/".join(s).startswith("BodyText/Section"):
            sections.append(s)
    sections.sort(key=lambda s: int(re.search(r"\d+", s[-1]).group(0)))
    out_parts: list[str] = []
    for s in sections:
        try:
            data = ole.openstream(s).read()
        except Exception:
            continue
        if compressed:
            try:
                data = zlib.decompress(data, -15)
            except Exception:
                continue
        pos = 0
        while pos + 4 <= len(data):
            h = struct.unpack("<I", data[pos:pos + 4])[0]
            pos += 4
            tag = h & 0x3FF
            size = (h >> 20) & 0xFFF
            if size == 0xFFF:
                if pos + 4 > len(data):
                    break
                size = struct.unpack("<I", data[pos:pos + 4])[0]
                pos += 4
            body = data[pos:pos + size]
            pos += size
            if tag == 67 and body:
                try:
                    s_ = body.decode("utf-16-le", errors="replace")
                    s_ = "".join(ch if (ord(ch) >= 0x20 or ch in "\n\t") else " " for ch in s_)
                    out_parts.append(s_)
                except Exception:
                    pass
    text = "\n".join(p.strip() for p in out_parts if p and p.strip())
    text = re.sub(r"^[a-zA-Z]{4,8}\s+$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ---------------- PDF ----------------

def pdf_extract_text(pdf_bytes: bytes) -> str:
    """PDF -> text. pdfplumber 우선, 실패시 PyPDF2."""
    if not pdf_bytes or pdf_bytes[:4] != b"%PDF":
        return ""
    # 1. pdfplumber
    try:
        import pdfplumber
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            texts = []
            for page in pdf.pages[:100]:  # 100페이지 상한
                try:
                    t = page.extract_text()
                    if t:
                        texts.append(t)
                except Exception:
                    continue
            txt = "\n".join(texts).strip()
            if len(txt) >= 40:
                return txt
    except Exception:
        pass
    # 2. PyPDF2
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(BytesIO(pdf_bytes))
        texts = []
        for page in reader.pages[:100]:
            try:
                t = page.extract_text()
                if t:
                    texts.append(t)
            except Exception:
                continue
        return "\n".join(texts).strip()
    except Exception:
        return ""


# ---------------- 게시판 view → 첨부 텍스트 ----------------

_ATTACH_HWP_RE = re.compile(
    r"""href=["']([^"'>\s]+\.(?:hwp|hwpx))["']""", re.I)
_ATTACH_PDF_RE = re.compile(
    r"""href=["']([^"'>\s]+\.pdf)["']""", re.I)
_DOWNLOAD_HWP_RE = re.compile(
    r"""href=["']([^"'>\s]*download\.php\?[^"'>\s]*\.hwp[^"'>\s]*)["']""", re.I)


def find_attachment_links(html: str, base_url: str) -> list[tuple[str, str]]:
    """게시판 view HTML에서 첨부 링크 추출 -> [(kind, url), ...].

    kind: 'hwp' | 'pdf'. download.php?atch_path=...hwp 패턴도 hwp로 잡음.
    """
    if not html:
        return []
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for m in _DOWNLOAD_HWP_RE.finditer(html):
        h = m.group(1).replace("&amp;", "&")
        full = urljoin(base_url, h)
        if full not in seen:
            seen.add(full)
            out.append(("hwp", full))
    for m in _ATTACH_HWP_RE.finditer(html):
        h = m.group(1).replace("&amp;", "&")
        full = urljoin(base_url, h)
        if full not in seen:
            seen.add(full)
            out.append(("hwp", full))
    for m in _ATTACH_PDF_RE.finditer(html):
        h = m.group(1).replace("&amp;", "&")
        full = urljoin(base_url, h)
        if full not in seen:
            seen.add(full)
            out.append(("pdf", full))
    return out


def fetch_attachments_text(html: str, base_url: str, max_attachments: int = 3) -> str:
    """게시판 view HTML -> 첨부 본문 텍스트 합본 (HWP+PDF). 실패하거나 첨부 없으면 빈문자."""
    links = find_attachment_links(html, base_url)
    if not links:
        return ""
    parts: list[str] = []
    for kind, url in links[:max_attachments]:
        data = safe_download(url, timeout=40)
        if not data:
            continue
        if kind == "hwp":
            t = hwp_extract_text(data)
        else:
            t = pdf_extract_text(data)
        if t and len(t) >= 40:
            parts.append(f"[첨부:{kind}] {t}")
    return "\n\n".join(parts).strip()
