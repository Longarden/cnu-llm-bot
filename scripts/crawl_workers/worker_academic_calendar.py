"""academic_calendar 보강 워커 (label 2 / B_academic).

목표: 충남대 2026학년도 학사일정(학사력)을 '구체적 날짜'로 수집하고, 특히
'기말고사 기간'을 답변 가능하게 만든다.

소스(전부 requests 200 확인, resp.content UTF-8 decode — 서버 헤더는 text/html
이지만 실제 바이트는 정상 UTF-8, 모지바케 없음):
  1) plus.cnu.ac.kr academic_calendar (year=2026)
       /_prog/academic_calendar/?site_dvs_cd=kr&menu_dvs_cd=05020101&year=2026
       -> div.fr_list 13개(헤더 1 + 1~12월). 각 항목 텍스트 = "MM.DD(요일) 행사명" 나열.
  2) plus.cnu.ac.kr 학사공지(sub07_0702) no=2513390 '2026학년도 제1학기 시험운영 안내'
       본문은 셸(JS)이고 실제 일정은 첨부 PDF(안내문.pdf)에 있음 -> fitz로 추출.
       핵심: 기말시험은 '담당교수가 정하며 하기방학(06.22) 전까지 실시 완료'.

설계 결정:
  - academic_calendar 는 <table> 없이 div.fr_list 안에 a 태그들로 날짜+행사가 들어있다.
    fr_list[0] 은 월 네비/헤더라 스킵, fr_list[1..12] 가 1~12월.
    월 인덱스 = enumerate 순서(첫 데이터 블록=1월) 로 매핑.
  - 검색 적중률을 위해 (a) 전체 학사력 1건, (b) 월별 12건, (c) 주제별
    요약 4건(학기 시작/종료·시험, 수강신청·정정·철회, 휴학·복학·등록, 계절학기·학위수여·공휴일)
    으로 분할 생성.
  - 시험 PDF 1건은 별도 doc(기말고사 기간 질의 대응).
  - 모든 텍스트 repair_encoding 통과(정상문은 그대로). original_text 30자+ 보장.

출력: data/crawled_staging/academic_calendar.json (+ .done)
실행:  py -3.13 scripts/crawl_workers/worker_academic_calendar.py
"""
import sys, json, re, io
from pathlib import Path
from datetime import datetime, timedelta

ROOT = Path('C:/Users/dmsak/cnu-llm-bot')
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

import requests
from bs4 import BeautifulSoup
from crawler_pipeline.text_repair import repair_encoding

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36',
    'Accept-Language': 'ko-KR,ko;q=0.9',
}
TIMEOUT = 30
NOW = datetime.utcnow().isoformat()
TODAY = NOW[:10]
# 학사력은 학년도 단위 고정 정보 -> 180일 유효(static)
VALID = (datetime.utcnow() + timedelta(days=180)).isoformat()

CAL_URL = ('https://plus.cnu.ac.kr/_prog/academic_calendar/'
           '?site_dvs_cd=kr&menu_dvs_cd=05020101&year=2026')
EXAM_POST_URL = 'https://plus.cnu.ac.kr/_prog/_board/?code=sub07_0702&mode=V&no=2513390'
EXAM_PDF_URL = ('https://plus.cnu.ac.kr/_prog/_board/common/download.php'
                '?code=sub07_0702&ntt_no=2513390&atch_no=1')

MONTH_NAMES = ['1월', '2월', '3월', '4월', '5월', '6월', '7월', '8월',
               '9월', '10월', '11월', '12월']


def get_utf8(url):
    """requests GET -> resp.content 를 UTF-8 로 강제 decode(헤더 무시)."""
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    return r.content.decode('utf-8'), r.content


def make_doc(url, title, text, date=TODAY):
    title = repair_encoding(title)
    text = repair_encoding(text)
    return {
        'source_url': url,
        'data_category': 'B_academic',
        'last_crawled_at': NOW,
        'valid_until': VALID,
        'freshness_tier': 'static',
        'original_text': text,
        'title': title,
        'content': text,
        'date': date,
    }


DATE_TOK = r'\d{1,2}\.\d{1,2}\([월화수목금토일]\)'


def split_events(block_text):
    """'MM.DD(요일) ... 행사명' 나열 텍스트를 개별 일정 줄로 분할.

    각 일정은 'MM.DD(요일)' 또는 'MM.DD(요일) ~ MM.DD(요일)' 로 시작한다.
    'A ~ B' 범위의 두 번째 날짜(B)는 분할하지 않는다.
    """
    s = re.sub(r'\s+', ' ', block_text).strip()
    # 범위의 두 번째 날짜('~ MM.DD(요일)') 전체를 placeholder 로 치환해 보호.
    protected = []

    def _hold(m):
        protected.append(m.group(0))
        return '\x00%d\x00' % (len(protected) - 1)

    s = re.sub(r'~\s*' + DATE_TOK, _hold, s)
    # 남은(=일정 시작) 날짜 토큰 앞에 줄바꿈.
    s = re.sub(r'(' + DATE_TOK + r')', r'\n\1', s)
    # placeholder 복원.
    s = re.sub(r'\x00(\d+)\x00', lambda m: protected[int(m.group(1))], s)
    lines = [l.strip() for l in s.split('\n') if l.strip()]
    return lines


def lead_month(block_text):
    """블록의 첫 'MM.' 에서 월 번호(1~12) 추출. 실패 시 None."""
    m = re.search(r'(\d{1,2})\.\d{1,2}\(', block_text)
    if not m:
        return None
    mm = int(m.group(1))
    return mm if 1 <= mm <= 12 else None


def parse_calendar():
    """academic_calendar 파싱 -> (전체텍스트, {월: [일정줄...]})."""
    html, _ = get_utf8(CAL_URL)
    soup = BeautifulSoup(html, 'html.parser')
    for t in soup(['script', 'style']):
        t.decompose()
    fr = soup.select('div.fr_list')
    if not fr:
        return '', {}
    # fr_list 중 날짜(\d+\.\d+)를 포함하는 블록만 '월 데이터'로 본다.
    month_blocks = []
    for d in fr:
        txt = d.get_text(' ', strip=True)
        if re.search(r'\d{1,2}\.\d{1,2}\(', txt):
            month_blocks.append(txt)
    # 월 매핑은 enumerate 순서가 아니라 각 블록의 '첫 날짜 MM.' 로 결정한다.
    # (블록0 = 전년 12월 계절학기 carryover 가 섞여 있어 순서 매핑 시 오프바이원 발생)
    # 같은 월로 떨어지는 블록은 줄 단위 합치고 중복 제거.
    by_month = {}
    for blk in month_blocks:
        mm = lead_month(blk)
        if mm is None:
            continue
        mname = MONTH_NAMES[mm - 1]
        for line in split_events(blk):
            by_month.setdefault(mname, [])
            if line not in by_month[mname]:
                by_month[mname].append(line)
    return month_blocks, by_month


def parse_exam_pdf():
    """시험운영 안내 PDF(fitz) 추출. 실패 시 ''. """
    try:
        import fitz
    except Exception:
        return ''
    try:
        r = requests.get(EXAM_PDF_URL, headers=HEADERS, timeout=40)
        if r.status_code != 200 or not r.content:
            return ''
        doc = fitz.open(stream=r.content, filetype='pdf')
        txt = ''
        for pg in doc:
            txt += pg.get_text() + '\n'
        doc.close()
        return repair_encoding(txt.strip())
    except Exception as e:
        print('  [exam pdf] 실패:', type(e).__name__, e, flush=True)
        return ''


# 주제별 요약: 어떤 키워드가 들어간 일정 줄을 모을지.
TOPIC_KEYWORDS = {
    '학기 개강·종강 및 시험·방학 일정': [
        '개강', '종강', '방학', '시험', '수업일수', '보강', '보충강의', '성적'],
    '수강신청·수강정정·수강철회 일정': [
        '수강신청', '예비수강', '수강신청 확인', '변경', '수강신청 취소',
        '폐강', '강의평가'],
    '휴학·복학·등록금 일정': [
        '휴학', '복학', '등록금', '등록기간', '분할납부', '추가등록'],
    '계절학기·학위수여식·공휴일 일정': [
        '계절학기', '학위수여', '입학식', '졸업', '신정', '설날', '추석',
        '대체공휴일', '한글날', '광복절', '개천절', '성탄절', '근로자의 날',
        '현충일', '어린이날', '석가탄신', '부처님'],
}


def build_topic_docs(by_month):
    """월별 일정 전체를 평탄화한 뒤 주제 키워드로 묶어 요약 doc 생성."""
    all_lines = []
    for i, m in enumerate(MONTH_NAMES):
        for line in by_month.get(m, []):
            all_lines.append(line)
    docs = []
    for topic, kws in TOPIC_KEYWORDS.items():
        hits = [l for l in all_lines if any(k in l for k in kws)]
        # 중복 제거(순서 유지)
        seen = set(); uniq = []
        for l in hits:
            if l not in seen:
                seen.add(l); uniq.append(l)
        if not uniq:
            continue
        body = ('충남대학교 2026학년도 학사일정 중 ' + topic + '입니다.\n'
                + '\n'.join(uniq))
        docs.append(make_doc(CAL_URL, f'충남대 2026학년도 {topic}', body))
    return docs


def main():
    out_dir = ROOT / 'data/crawled_staging'
    out_dir.mkdir(parents=True, exist_ok=True)
    docs = []

    # 1) 학사력 파싱
    try:
        month_blocks, by_month = parse_calendar()
        print(f'  [calendar] 월 데이터 블록 {len(month_blocks)}개', flush=True)
    except Exception as e:
        print('  [calendar] 실패:', type(e).__name__, e, flush=True)
        month_blocks, by_month = [], {}

    if by_month:
        # (a) 전체 학사력 1건
        full_lines = []
        for m in MONTH_NAMES:
            ev = by_month.get(m, [])
            if ev:
                full_lines.append(f'[{m}]')
                full_lines.extend(ev)
        full_text = ('충남대학교 2026학년도 학사일정(학사력) 전체입니다. '
                     '날짜는 MM.DD(요일) 형식입니다.\n' + '\n'.join(full_lines))
        docs.append(make_doc(CAL_URL, '충남대 2026학년도 학사일정(학사력) 전체', full_text))

        # (b) 월별 12건
        for m in MONTH_NAMES:
            ev = by_month.get(m, [])
            if not ev:
                continue
            body = (f'충남대학교 2026학년도 {m} 학사일정입니다. '
                    f'날짜는 MM.DD(요일) 형식입니다.\n' + '\n'.join(ev))
            if len(body) >= 30:
                docs.append(make_doc(CAL_URL, f'충남대 2026학년도 {m} 학사일정', body))

        # (c) 주제별 요약
        docs.extend(build_topic_docs(by_month))

    # 2) 기말고사/시험 운영 (PDF) — '기말고사 기간' 질의 핵심
    exam_pdf = parse_exam_pdf()
    if exam_pdf and len(exam_pdf) >= 30:
        # 검색 키워드 보강(중간고사/기말고사/시험기간) 헤더를 앞에 덧붙임.
        body = ('충남대학교 2026학년도 제1학기 중간고사·기말고사(시험) 기간 및 '
                '시험 운영 안내입니다. 충남대는 시험기간을 학교 차원에서 일괄 '
                '고정하지 않고, 교과목 담당교수가 정하되 기말시험은 하기방학 전까지 '
                '(2026학년도 하기방학 시작 06.22(월)) 실시 완료합니다.\n\n' + exam_pdf)
        docs.append(make_doc(EXAM_POST_URL,
                             '충남대 2026학년도 제1학기 시험(중간·기말고사) 운영 안내',
                             body))
        print('  [exam] PDF 추출 OK', len(exam_pdf), '자', flush=True)
    else:
        print('  [exam] PDF 추출 실패/빈문서', flush=True)

    # 저장
    out_path = out_dir / 'academic_calendar.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(docs, f, ensure_ascii=False, indent=2)
    (out_dir / 'academic_calendar.done').write_text(str(len(docs)), encoding='utf-8')

    # 검증
    han = sum(sum(1 for c in (d['content'] or '') if '가' <= c <= '힣') for d in docs)
    fffd = sum((d['content'] or '').count('�') + (d['title'] or '').count('�') for d in docs)
    short = sum(1 for d in docs if len((d['original_text'] or '')) < 30)
    keys_ok = all(set(d) >= {'source_url', 'data_category', 'last_crawled_at',
                             'valid_until', 'freshness_tier', 'original_text',
                             'title', 'content', 'date'} for d in docs)
    print('\n=== academic_calendar 결과 ===')
    print(f'  문서 수: {len(docs)}')
    print(f'  한글 코드포인트: {han}  U+FFFD: {fffd}  30자미만: {short}  9키OK: {keys_ok}')
    print('  샘플 제목:')
    for d in docs[:12]:
        print('   -', d['title'])
    if exam_pdf:
        print('   - (시험 PDF 포함)')


if __name__ == '__main__':
    main()
