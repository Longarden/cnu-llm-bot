import requests, re, sys, io
from bs4 import BeautifulSoup
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120 Safari/537.36"}

def get(url, t=20, retries=1):
    last=None
    for _ in range(retries+1):
        try:
            r=requests.get(url,headers=H,timeout=t,allow_redirects=True)
            return r
        except Exception as e:
            last=e
    raise last

# candidate dept notice boards (jwxe pattern). probe multiple path guesses.
cands = {
 "ee_전자": ["https://ee.cnu.ac.kr/ee/community/notice.do"],
 "me_기계": ["https://me.cnu.ac.kr/me/board/notice.do","https://me.cnu.ac.kr/me/community/notice.do","https://me.cnu.ac.kr/me/notice/list.do"],
 "biz_경영": ["https://biz.cnu.ac.kr/biz/board/notice.do","https://biz.cnu.ac.kr/biz/community/notice.do","https://biz.cnu.ac.kr/biz/notice/list.do"],
 "mse_신소재": ["https://mse.cnu.ac.kr/mse/board/notice.do","https://mse.cnu.ac.kr/mse/community/notice.do","https://mse.cnu.ac.kr/mse/notice/list.do"],
 "math_수학": ["https://math.cnu.ac.kr/math/board/notice.do","https://math.cnu.ac.kr/math/community/notice.do","https://math.cnu.ac.kr/math/notice/list.do"],
 "cnustudent": ["https://cnustudent.cnu.ac.kr/cnustudent/notice/notice.do"],
}
for name, urls in cands.items():
    for url in urls:
        try:
            r=get(url)
            t=r.content.decode("utf-8","replace")
            soup=BeautifulSoup(t,"html.parser")
            rows=soup.select("table tbody tr, .board-list li, .b-list-table tbody tr")
            # find first row with a link + text
            sample=""
            for row in rows:
                a=row.select_one("a")
                if a and a.get_text(strip=True):
                    sample=a.get_text(strip=True)[:40]; break
            print(f"{r.status_code} | {name:12} | rows={len(rows):3} | first='{sample}' | {url}")
        except Exception as e:
            print(f"ERR | {name:12} | {type(e).__name__} | {url}")
