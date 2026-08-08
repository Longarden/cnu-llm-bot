# -*- coding: utf-8 -*-
"""grad_rules 워커: 졸업요건(label 0) 보강. 출력 -> ub_grad_rules.json

소스(모두 200 확인, 학부 한정 / 대학원 제외):
 - plus.cnu.ac.kr 학칙(mng_no=281)·학부 학사운영규정(mng_no=282) view_pop -> B_academic
   (주의: mng_no 283~294 는 대학원/경영대학원/교육대학원 등 '대학원' 규정이라 제외)
 - computer.cnu.ac.kr 졸업요건/교육과정 게시판 article (.fr-view) -> F_department
   (전공/교양/복수전공/편입/프로젝트/포트폴리오 등 구체 수치·요건 포함 article만)

규칙: 9키(_make_doc 동일), resp.content를 UTF-8 decode, original_text 30자 이상,
      U+FFFD 0건. 배정 staging 1개(ub_grad_rules.json)만 기록. git 금지.
"""
import json
import re
import time
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) crawl-grad-rules"}
OUT = r"C:/Users/dmsak/cnu-llm-bot/data/crawled_staging/ub_grad_rules.json"


def fetch(url, retries=3):
    """GET + 재시도. resp.content를 UTF-8로 decode(서버 charset 헤더 무시)."""
    last = None
    for i in range(retries):
        try:
            r = requests.get(url, timeout=30, headers=UA)
            r.raise_for_status()
            return r.content.decode("utf-8")  # 충남대 페이지는 실제 UTF-8
        except Exception as e:
            last = e
            time.sleep(1.5 * (i + 1))
    raise last


def clean(text):
    return re.sub(r"\s+", " ", text).strip()


def make_doc(category_id, title, content, source_url, now, valid, date=""):
    return {
        "source_url": source_url,
        "data_category": category_id,
        "last_crawled_at": now,
        "valid_until": valid,
        "freshness_tier": "semi_static",
        "original_text": content,
        "title": title,
        "content": content,
        "date": date or now[:10],
    }


def crawl_rule_popup(mng_no, name, now, valid):
    """plus.cnu 학칙/학부 학사운영규정 view_pop. 본문 텍스트 추출."""
    url = f"https://plus.cnu.ac.kr/_prog/rule/view_pop.php?mng_no={mng_no}"
    html = fetch(url)
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style"]):
        t.decompose()
    body = clean(soup.get_text(" ", strip=True))
    if len(body) < 30:
        return []
    # 대학원 규정 가드: 본문이 '대학원' 운영부서면 학부 한정 위반 -> 버림
    if re.search(r"운영 및 관리부서\s*\S*대학원", body):
        return []
    title = f"충남대학교 {name} (졸업·이수학점 관련 학사규정)"
    content = f"[{name}] {body[:1800]}"
    return [make_doc("B_academic", title, content, url, now, valid)]


def crawl_cai_article(article_no, now, valid):
    """computer.cnu 졸업요건 게시판 article 본문(.fr-view) 추출."""
    url = f"https://computer.cnu.ac.kr/computer/edu/requirements.do?mode=view&articleNo={article_no}"
    html = fetch(url)
    soup = BeautifulSoup(html, "html.parser")
    title = ""
    m = re.search(r"<title>(.*?)</title>", html, re.S)
    if m:
        raw = clean(m.group(1))
        mm = re.search(r"\(\s*(.*?)\s*\)\s*$", raw)
        title = mm.group(1) if mm else raw
    node = soup.select_one(".fr-view, .b-content-box, .b-content")
    if not node:
        return []
    body = clean(node.get_text(" ", strip=True))
    if len(body) < 30:
        return []
    full_title = f"[컴퓨터인공지능학부 졸업요건] {title}" if title else "[컴퓨터인공지능학부 졸업요건]"
    return [make_doc("F_department", full_title, body[:2200], url, now, valid)]


def main():
    now = datetime.utcnow().isoformat()
    valid = (datetime.utcnow() + timedelta(days=180)).isoformat()
    docs = []

    # 1) 학부 대상 학칙 / 학부 학사운영규정 (대학원 mng_no 283~ 제외)
    for mng, name in [(281, "학칙"), (282, "학사운영규정")]:
        try:
            docs += crawl_rule_popup(mng, name, now, valid)
            print(f"[ok] rule mng_no={mng} ({name})")
        except Exception as e:
            print(f"[skip] rule mng_no={mng}: {e}")

    # 2) 컴퓨터인공지능학부 졸업요건/교육과정 article
    #    구체 수치·요건 포함 article (전공/교양/복수전공/편입/프로젝트/포트폴리오)
    cai_articles = [
        586423,  # 학부·인공지능학과 졸업에 관한 학과 규정 안내
        569099,  # 졸업요건 본문(교양 48/42학점, 글쓰기 2학점 등)
        569097,  # 비교과 졸업요건: 프로젝트 교과목/트랙 이수
        569096,  # 비교과 졸업요건: 포트폴리오
        528333,  # 졸업요건(교직 기본이수 21학점 등)
        576049,  # 2026 교육과정표/전공이수체계
        576000,  # 2026 교육과정 관련
        285160,  # 2021학년도 이후 입학자 프로젝트교과목 및 트랙 이수
        255183,  # 2018학년도 이후 입학자 비교과 졸업요건(포트폴리오 제출 시기)
        519805,  # 인공지능학과·컴퓨터융합학부 상호 부·복수전공 졸업요건
        205887,  # 2021학년도 교양 교과목 변경 사항(진로설계 등)
        98307,   # 2017학년도 이후 입학자 인문학 8학점 이상 이수 졸업요건
        98300,   # 2013학번 인증종료: 교양 이수학점 46->36 하향
        98302,   # 졸업관리 교양 교육과정 이수 매뉴얼(졸업자가진단)
        98298,   # 글로벌영어 이수면제 요건 변경(학칙개정)
    ]
    seen = set()
    for art in cai_articles:
        try:
            ds = crawl_cai_article(art, now, valid)
            kept = 0
            for d in ds:
                key = d["content"][:120]
                if key in seen:
                    continue
                seen.add(key)
                docs.append(d)
                kept += 1
            print(f"[ok] cai article={art} ({kept} doc)")
        except Exception as e:
            print(f"[skip] cai article={art}: {e}")
        time.sleep(0.6)

    # 검증: original_text >= 30, U+FFFD 0
    clean_docs = []
    ufffd_total = 0
    for d in docs:
        ot = d["original_text"]
        u = ot.count("�") + d["title"].count("�")
        ufffd_total += u
        if len(ot) >= 30 and u == 0:
            clean_docs.append(d)

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(clean_docs, f, ensure_ascii=False, indent=2)

    print("=" * 50)
    print(f"written: {len(clean_docs)} docs -> {OUT}")
    print(f"U+FFFD total: {ufffd_total}")
    for d in clean_docs:
        print("  -", d["data_category"], "|", d["title"][:55])


if __name__ == "__main__":
    main()
