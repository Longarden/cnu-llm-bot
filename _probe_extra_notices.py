import requests, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}

cands = [
    # 비교과 / CCAP / 학생지원
    ("CCAP비교과", "https://ccap.cnu.ac.kr/"),
    ("비교과통합", "https://ccap.cnu.ac.kr/ccap/program/list.do"),
    ("학생지원cnustudent", "https://cnustudent.cnu.ac.kr/"),
    ("cnustudent공지", "https://cnustudent.cnu.ac.kr/cnustudent/notice/notice.do"),
    ("dream비교과", "https://dream.cnu.ac.kr/"),
    ("plus학생지원", "https://plus.cnu.ac.kr/_prog/_board/?code=sub07_0703"),
    # 학과 공지
    ("전자ee", "https://ee.cnu.ac.kr/ee/notice/notice01.do"),
    ("전자ee공지2", "https://ee.cnu.ac.kr/ee/community/notice.do"),
    ("기계me", "https://mech.cnu.ac.kr/mech/notice/notice.do"),
    ("기계me2", "https://me.cnu.ac.kr/me/notice/notice.do"),
    ("경영biz", "https://biz.cnu.ac.kr/biz/notice/notice.do"),
    ("경영business", "https://business.cnu.ac.kr/business/notice/notice.do"),
    ("신소재mse", "https://mse.cnu.ac.kr/mse/notice/notice.do"),
    ("수학math", "https://math.cnu.ac.kr/math/notice/notice.do"),
    ("수학science", "https://science.cnu.ac.kr/"),
    # 컴퓨터(참고용, K_notices와 다른 페이지)
    ("컴인공scholarship", "https://computer.cnu.ac.kr/computer/notice/scholarship.do"),
]

for name, url in cands:
    try:
        r = requests.get(url, headers=H, timeout=15, allow_redirects=True)
        txt = r.content.decode("utf-8", errors="replace")
        has_tr = txt.count("<tr") + txt.count("board-list")
        print(f"{r.status_code} | {name:18} | tr/list={has_tr:4} | final={r.url[:70]}")
    except Exception as e:
        print(f"ERR | {name:18} | {type(e).__name__}: {str(e)[:50]} | {url}")
