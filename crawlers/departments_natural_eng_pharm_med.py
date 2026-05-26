"""자연대/공대/농생대/약대/의대/간호대/수의대/생활대 전 학과 크롤러.

departments_humanities_social.py 와 동일한 구조:
- DEPARTMENTS: 단과대학별 base/intro_paths/notice_path/depts(이름, 경로)
- trafilatura 기반 본문 추출(crawler_pipeline.body_extractor)
- repair_encoding으로 모지바케 복구
- 9키 표준 dict + (department, college, attachment_type) 부가 키

저장 경로: data/crawled_staging/departments_natural.json
- 통합은 통합 담당자가 수행. __init__.py에는 추가하지 않음.

원칙: 절대 학과/교수 정보를 지어내지 않는다. fetch/추출 실패시 빈 결과로 처리하고 리포트만 남긴다.
"""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

# 프로젝트 루트를 path에 추가(직접 실행 호환)
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from crawler_pipeline.body_extractor import fetch_html, extract_main_text  # noqa: E402
from crawler_pipeline.text_repair import repair_encoding  # noqa: E402


# 실제 fetch 검증된 단과대 도메인 + 학과 URL
DEPARTMENTS = {
    '자연과학대학': {
        'base': 'https://cns.cnu.ac.kr',
        'intro_paths': [
            '/cns/intro/greetings.do',
            '/cns/intro/history.do',
            '/cns/intro/plan.do',
            '/cns/intro/dean.do',
            '/cns/intro/administration.do',
            '/cns/intro/location.do',
        ],
        'notice_path': '/cns/community/notice.do',
        'depts': [
            ('수학과', '/cns/department/les01.do'),
            ('정보통계학과', '/cns/department/les02.do'),
            ('물리학과', '/cns/department/les03.do'),
            ('천문우주과학과', '/cns/department/les04.do'),
            ('화학과', '/cns/department/les05.do'),
            ('생화학과', '/cns/department/les06.do'),
            ('지질환경과학과', '/cns/department/les07.do'),
            ('해양환경과학과', '/cns/department/les08.do'),
            ('스포츠과학과', '/cns/department/les09.do'),
            ('무용학과', '/cns/department/les10.do'),
            ('반도체융합학과', '/cns/department/les11.do'),
        ],
    },
    '공과대학': {
        'base': 'https://eng.cnu.ac.kr',
        'intro_paths': [
            '/eng/intro/greeting.do',
            '/eng/intro/history.do',
            '/eng/intro/vision.do',
            '/eng/intro/organ.do',
            '/eng/intro/office.do',
            '/eng/intro/location.do',
        ],
        'notice_path': '/eng/information/notice.do',
        'depts': [
            ('항공우주공학과', '/eng/department/aerospace.do'),
            ('응용화학공학과', '/eng/department/appchemistry.do'),
            ('건축학과', '/eng/department/archi.do'),
            ('건축공학과', '/eng/department/archieng.do'),
            ('자율운항시스템공학과', '/eng/department/autovehicle.do'),
            ('토목공학과', '/eng/department/civil.do'),
            ('컴퓨터인공지능학부(공대분원)', '/eng/department/computerconverge.do'),
            ('전기공학과', '/eng/department/electrical.do'),
            ('전자공학과', '/eng/department/electronics.do'),
            ('에너지공학과', '/eng/department/energy.do'),
            ('환경공학과', '/eng/department/envior.do'),
            ('정보통신융합학부', '/eng/department/info.do'),
            ('신소재공학과', '/eng/department/materials.do'),
            ('기계공학부', '/eng/department/mechanical.do'),
            ('메카트로닉스공학과', '/eng/department/mechatronics.do'),
            ('선박해양공학과', '/eng/department/oceanarchi.do'),
            ('유기재료공학과', '/eng/department/organmaterials.do'),
            ('전파정보통신공학과', '/eng/department/radioinfo.do'),
            ('스마트시티건축공학과', '/eng/department/smartcity.do'),
        ],
    },
    '농업생명과학대학': {
        'base': 'https://cals.cnu.ac.kr',
        'intro_paths': [
            '/cals/intro/info/greeting.do',
            '/cals/intro/info/spec.do',
            '/cals/intro/history-now.do',
            '/cals/intro/vision/vision.do',
            '/cals/intro/vision/vision02.do',
            '/cals/intro/organize/info.do',
            '/cals/intro/organize/info02.do',
            '/cals/intro/organize/info03.do',
            '/cals/intro/dean.do',
            '/cals/intro/symbol.do',
        ],
        'notice_path': '/cals/community/notice.do',
        'depts': [
            ('응용생물학과', '/cals/part/abio.do'),
            ('농업경제학과', '/cals/part/agrieco.do'),
            ('동물바이오시스템과학과', '/cals/part/ani-bio.do'),
            ('동물자원생명과학과', '/cals/part/ani-res.do'),
            ('지역환경토목학과', '/cals/part/are.do'),
            ('생물환경화학과', '/cals/part/bec.do'),
            ('스마트농업시스템기계공학과', '/cals/part/bme.do'),
            ('식물자원학과', '/cals/part/crop.do'),
            ('산림환경자원학과', '/cals/part/forest.do'),
            ('식품공학과', '/cals/part/fst.do'),
            ('원예학과', '/cals/part/horti.do'),
            ('환경소재공학과', '/cals/part/wood.do'),
            ('자유전공(농생대)', '/cals/major/free.do'),
        ],
    },
    '약학대학': {
        'base': 'https://pharm.cnu.ac.kr',
        'intro_paths': [
            '/pharm/intro/greetings.do',
            '/pharm/intro/history.do',
            '/pharm/intro/history01.do',
            '/pharm/intro/goal.do',
            '/pharm/intro/talent.do',
            '/pharm/intro/plan01.do',
            '/pharm/intro/plan02.do',
            '/pharm/intro/plan03.do',
            '/pharm/intro/oranization.do',
            '/pharm/intro/administstration.do',
            '/pharm/intro/location.do',
        ],
        'notice_path': '/pharm/community/notice.do',
        'depts': [
            ('약학대학(학부)', '/pharm/intro/faculty01.do'),
            ('약학대학 - 교과과정/대학원', '/pharm/grad/major.do'),
            ('약학대학 - 부속실험실', '/pharm/lab/info.do'),
            ('약학대학 - 약초원', '/pharm/affiliate/herbgarden/history.do'),
            ('약학대학 - 부설약국', '/pharm/affiliate/pham/history.do'),
        ],
    },
    '의과대학': {
        'base': 'https://medicine.cnu.ac.kr',
        'intro_paths': [
            '/medicine/intro/greeting.do',
            '/medicine/intro/history.do',
            '/medicine/intro/plan01.do',
            '/medicine/intro/responsibility.do',
            '/medicine/intro/organ.do',
            '/medicine/intro/introduce-undergrad.do',
            '/medicine/intro/introduce-grad.do',
            '/medicine/intro/brochure.do',
            '/medicine/intro/location.do',
        ],
        'notice_path': '/medicine/info/notice.do',
        'depts': [
            ('의과대학 - 학부(의예/의학과)', '/medicine/intro/introduce-undergrad.do'),
            ('의과대학 - 교수진(전임)', '/medicine/intro/faculty01.do'),
            ('의과대학 - 교수진(05)', '/medicine/intro/faculty05.do'),
            ('의과대학 - 대학원 일반', '/medicine/grad/intro-grad01.do'),
            ('의과대학 - 대학원 1', '/medicine/grad/introduce-grad01.do'),
            ('의과대학 - 대학원 2', '/medicine/grad/introduce-grad02.do'),
            ('의과대학 - 대학원 3', '/medicine/grad/introduce-grad03.do'),
            ('의과대학 - 대학원 4', '/medicine/grad/introduce-grad04.do'),
            ('의과대학 - 대학원 5', '/medicine/grad/introduce-grad05.do'),
            ('의과대학 - 대학원 6', '/medicine/grad/introduce-grad06.do'),
            ('의과대학 - 의학전공', '/medicine/grad/major-medicine.do'),
            ('의과대학 - 의과학전공', '/medicine/grad/major-science.do'),
        ],
    },
    '간호대학': {
        'base': 'https://nursing.cnu.ac.kr',
        'intro_paths': [
            '/nursing1/intro/greetings.do',
            '/nursing1/intro/intro.do',
            '/nursing1/intro/history.do',
            '/nursing1/intro/plan.do',
            '/nursing1/intro/vision.do',
            '/nursing1/intro/structure.do',
            '/nursing1/intro/location.do',
        ],
        'notice_path': '/nursing1/announce/notice.do',
        'depts': [
            ('간호학과(학부)', '/nursing1/edu/under.do'),
            ('간호학과 - 교과과정', '/nursing1/edu/curriculum.do'),
            ('간호학과 - 교수진', '/nursing1/intro/faculty01.do'),
            ('간호학과 - 대학원(석사)', '/nursing1/edu/master.do'),
            ('간호학과 - 대학원(박사/일반)', '/nursing1/edu/grad-master.do'),
            ('간호학과 - 학위논문', '/nursing1/edu/thesis-2017.do'),
        ],
    },
    '수의과대학': {
        'base': 'https://vetmed.cnu.ac.kr',
        'intro_paths': [
            '/vetmed/intro/greetings.do',
            '/vetmed/intro/introduction.do',
            '/vetmed/intro/history.do',
            '/vetmed/intro/leader.do',
            '/vetmed/intro/department.do',
            '/vetmed/intro/organ.do',
            '/vetmed/intro/office.do',
            '/vetmed/intro/contacts.do',
            '/vetmed/intro/location.do',
            '/vetmed/intro/map.do',
            '/vetmed/intro/traffic.do',
        ],
        'notice_path': '/vetmed/community/notice.do',
        'depts': [
            ('수의예과/수의학과', '/vetmed/info/course01.do'),
            ('수의과대학 - 교과목 소개2', '/vetmed/info/course02.do'),
            ('수의과대학 - 교과목 소개3', '/vetmed/info/course03.do'),
            ('수의과대학 - 졸업요건', '/vetmed/info/condition.do'),
            ('수의과대학 - 학사일정(학부)', '/vetmed/info/calendar-undergrad.do'),
            ('수의과대학 - 학사일정(대학원)', '/vetmed/info/calendar-grad.do'),
            ('수의과대학 - 대학원1', '/vetmed/info/grad01.do'),
            ('수의과대학 - 대학원2', '/vetmed/info/grad02.do'),
            ('수의과대학 - 대학원3', '/vetmed/info/grad03.do'),
        ],
    },
    '생활과학대학': {
        'base': 'https://homeco.cnu.ac.kr',
        'intro_paths': [
            '/homeco/intro/greetings.do',
            '/homeco/intro/history.do',
            '/homeco/intro/plan.do',
            '/homeco/intro/object.do',
            '/homeco/intro/organ.do',
            '/homeco/intro/team.do',
            '/homeco/intro/location.do',
        ],
        'notice_path': '/homeco/community/notice.do',
        'depts': [
            ('소비자학과', '/homeco/department/cli.do'),
            ('의류학과', '/homeco/department/cloth.do'),
            ('식품영양학과', '/homeco/department/fdnutri.do'),
            ('생활과학대학 - 일반대학원', '/homeco/department/grad.do'),
            ('생활과학대학 - 교육대학원', '/homeco/department/grad-edu.do'),
            ('생활과학대학 - 산업대학원', '/homeco/department/grad-industry.do'),
        ],
    },
}

SKIP_KW = ['바로가기', '주메뉴', '서브메뉴', '모바일 메뉴', '번역이 완료',
           '사이트맵', '로그인', '통합검색', 'CNU With U', '발전기금', '도서관',
           '정보화본부', '충남대학교', '본문 바로가기']


def _chunk_text(text: str, chunk_size: int = 400) -> list[str]:
    """trafilatura 본문을 chunk_size(approx) 문자 단위로 조각낸다."""
    lines = [l.strip() for l in text.splitlines() if len(l.strip()) > 8]
    lines = [l for l in lines if not any(kw in l for kw in SKIP_KW)]
    if not lines:
        return []
    chunks, buf, buf_len = [], [], 0
    for line in lines:
        buf.append(line)
        buf_len += len(line)
        if buf_len >= chunk_size:
            chunks.append('\n'.join(buf))
            buf, buf_len = [], 0
    if buf and buf_len >= 20:
        chunks.append('\n'.join(buf))
    return chunks


def _fetch_text(url: str, timeout: int = 20, retries: int = 2) -> str | None:
    """url -> trafilatura 본문 텍스트. 일시적 네트워크 실패시 1회 재시도. 최종 실패시 None.

    크롤러 파이프라인의 fetch_html(인코딩 보정) + extract_main_text(trafilatura) 사용.
    추가로 repair_encoding을 한번 더 적용해 모지바케 잔재 제거.
    """
    html = None
    for attempt in range(retries):
        try:
            html = fetch_html(url, timeout=timeout)
            break
        except Exception:
            html = None
    if html is None:
        return None
    txt = extract_main_text(html, min_len=30)
    if not txt:
        return None
    return repair_encoding(txt)


def _make_doc(title: str, content: str, source_url: str,
              department: str, college: str,
              now: str, valid: str, today: str) -> dict:
    """표준 9키 + 분류용 부가키."""
    return {
        'source_url': source_url,
        'data_category': 'F_department',
        'last_crawled_at': now,
        'valid_until': valid,
        'freshness_tier': 'semi_static',
        'original_text': content,
        'title': title,
        'content': content,
        'date': today,
        'department': department,
        'college': college,
        'attachment_type': 'text',
    }


def _crawl_page(url: str, title: str, department: str, college: str,
                now: str, valid: str, today: str) -> list[dict]:
    text = _fetch_text(url)
    if not text:
        return []
    docs = []
    for chunk in _chunk_text(text):
        docs.append(_make_doc(title, chunk, url, department, college, now, valid, today))
    return docs


def crawl_all(now: str, valid: str, today: str) -> tuple[list[dict], dict]:
    all_docs: list[dict] = []
    summary: dict = {}

    for college, info in DEPARTMENTS.items():
        print(f'\n=== {college} 크롤링 시작 ===', flush=True)
        base = info['base']
        college_docs: list[dict] = []
        college_summary: dict = {}

        # 단과대학 소개 페이지(여러 개)
        intro_total = 0
        for path in info.get('intro_paths', []):
            url = base + path
            docs = _crawl_page(url, f'{college} - 소개',
                               college, college, now, valid, today)
            college_docs.extend(docs)
            intro_total += len(docs)
        college_summary['__intro__'] = intro_total
        print(f'  [intro] {intro_total} 청크', flush=True)

        # 공지사항 (목록 페이지에서 본문만 추출 - 헤드라인 정도)
        notice_path = info.get('notice_path')
        if notice_path:
            url = base + notice_path
            docs = _crawl_page(url, f'{college} - 공지사항',
                               college, college, now, valid, today)
            college_docs.extend(docs)
            college_summary['__notice__'] = len(docs)
            print(f'  [notice] {len(docs)} 청크', flush=True)

        # 학과별 페이지
        for dept_name, dept_path in info['depts']:
            if dept_path.startswith('http'):
                dept_url = dept_path
            else:
                dept_url = base + dept_path
            docs = _crawl_page(dept_url, f'{dept_name} - 학과소개',
                               dept_name, college, now, valid, today)
            college_docs.extend(docs)
            college_summary[dept_name] = len(docs)
            status = 'OK' if docs else '수집실패'
            print(f'  [{dept_name}] {len(docs)} 청크 ({status})', flush=True)

        all_docs.extend(college_docs)
        summary[college] = college_summary
        print(f'  => {college} 소계: {len(college_docs)} 청크', flush=True)

    return all_docs, summary


def main():
    now = datetime.utcnow().isoformat()
    valid = (datetime.utcnow() + timedelta(days=14)).isoformat()
    today = now[:10]

    all_docs, summary = crawl_all(now, valid, today)

    out_path = Path('C:/Users/dmsak/cnu-llm-bot/data/crawled_staging/departments_natural.json')
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(all_docs, f, ensure_ascii=False, indent=2)

    print('\n=== 크롤링 완료 ===')
    print(f'총 청크: {len(all_docs)}')
    print(f'저장 경로: {out_path}')
    total_depts = 0
    failed_depts = []
    for college, dept_map in summary.items():
        print(f'\n{college}:')
        for key, cnt in dept_map.items():
            print(f'  {key}: {cnt} 청크')
            if not key.startswith('__'):
                total_depts += 1
                if cnt == 0:
                    failed_depts.append(f'{college}/{key}')
    print(f'\n총 학과(엔트리) 수: {total_depts}')
    if failed_depts:
        print(f'수집실패 항목 ({len(failed_depts)}):')
        for fd in failed_depts:
            print(f'  - {fd}')
    return all_docs, summary, str(out_path)


if __name__ == '__main__':
    main()
