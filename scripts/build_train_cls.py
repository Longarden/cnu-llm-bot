"""질문유형 분류기(Task1) 학습셋 합성 → data/cls/train.json + valid.json.

과제 라벨: 졸업요건=0, 학교공지=1, 학사일정=2, 식단=3, 통학/셔틀=4.
방법: 카테고리별 질문 템플릿 × 슬롯(크롤 데이터/상식 엔티티) 조합으로 다양화 →
      dedup → 셔플 → 90/10 train/valid 분리. API 없이 결정적(seed 고정).
출력 포맷(과제 p9): [{"question": "...", "label": N}, ...]

실행: python scripts/build_train_cls.py
"""
import sys, json, re, random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

ALL = ROOT / 'data' / 'crawled' / 'all_dedup.json'
OUT = ROOT / 'data' / 'cls'
OUT.mkdir(parents=True, exist_ok=True)
RNG = random.Random(42)

# ── 슬롯 값: 상식 엔티티 + 크롤 데이터에서 보강 ────────────────────
DINING_HALLS = ['제1학생회관', '제2학생회관', '제3학생회관', '생활관식당',
                '교직원식당', '학생회관', '푸드코트', '기숙사 식당', '백마교양교육관',
                '제4학생회관', '전망 좋은 식당']
MEALS = ['오늘', '내일', '이번주', '월요일', '화요일', '수요일', '목요일', '금요일',
         '점심', '저녁', '아침', '다음주', '주말']
DEPTS = ['컴퓨터융합학부', '컴퓨터공학과', '전자공학과', '경영학부', '국어국문학과',
         '수학과', '간호학과', '약학과', '기계공학부', '화학과', '전기공학과',
         '신소재공학과', '생명시스템과학과', '심리학과', '행정학부', '무역학과']
MAJOR_TERMS = ['전공', '복수전공', '부전공', '교양', '졸업논문', '졸업시험',
               '전공필수', '전공선택', '복수전공자', '편입생']
SCHED_TERMS = ['수강신청', '수강정정', '수강철회', '계절학기 신청', '성적정정',
               '개강', '종강', '중간고사', '기말고사', '휴학 신청', '복학 신청',
               '재수강 신청', '교양 신청', '학위수여식', '오리엔테이션']
SEM = ['1학기', '2학기', '이번 학기', '다음 학기', '이번학기', '여름 계절학기',
       '겨울 계절학기', '2026학년도 1학기']
ROUTE = ['정문', '대학로', '유성', '궁동', '대덕캠퍼스', '보운캠퍼스', '대전역',
         '서대전', '캠퍼스 순환', '기숙사', '공대']
DAY = ['평일', '주말', '오늘', '내일', '시험기간', '공휴일', '방학 중', '토요일']
TOPIC = ['장학금', '등록금', '취업', '수강', '기숙사', '도서관', '국제교류',
         '근로장학', '비교과', '학자금대출']

# 카테고리별 질문 템플릿. {slot} 은 위 리스트에서 채움.
TEMPLATES = {
    0: [  # 졸업요건
        '졸업하려면 몇 학점을 들어야 하나요?',
        '졸업까지 몇 학점 들어야 해?',
        '{major} 졸업 요건이 어떻게 되나요?',
        '{dept} 졸업학점이 몇 점이에요?',
        '{major} 이수 기준 알려줘',
        '교양 몇 학점 들어야 졸업해요?',
        '졸업 요건 좀 알려주세요',
        '전공 필수 학점이 얼마인가요?',
        '{dept} 졸업하려면 뭐가 필요해?',
        '복수전공 하면 졸업학점 어떻게 돼?',
        '졸업논문 꼭 써야 하나요?',
        '졸업 자격 요건이 뭐예요?',
        '{dept} {major} 졸업 요건 알려줘',
        '{sem}에 졸업하려면 학점 얼마나 필요해?',
        '{dept} 졸업 필수 과목이 뭐예요?',
        '{major} 최소 이수학점이 얼마죠?',
        '졸업하려면 {major} 몇 학점 들어야 해?',
        '{dept} 졸업 사정 기준 알려줘',
        '{major} 이수 학점 어떻게 채워요?',
    ],
    1: [  # 학교/학과 공지
        '이번에 올라온 공지사항 어디서 볼 수 있어요?',
        '최근 공지 뭐 올라왔어?',
        '{dept} 공지사항 알려줘',
        '학교 공지 어디서 확인해요?',
        '새로 올라온 공지 있어?',
        '{dept} 공지 어디서 봐?',
        '{topic} 공지 어디서 확인해요?',
        '{topic} 관련 공지 올라온 거 있어?',
        '{dept} {topic} 공지 알려줘',
        '학과 공지사항 보고 싶어요',
        '가장 최근 공지가 뭐예요?',
        '공지사항 게시판 어디 있어요?',
        '이번주 공지 알려줄래?',
        '학교에서 올린 안내 어디서 봐?',
        '{topic} 안내문 어디 있어요?',
        '{dept} 새 공지 있나요?',
    ],
    2: [  # 학사일정
        '이번 학기 수강신청은 언제 시작하나요?',
        '{sched} 기간이 언제예요?',
        '{sched} 언제부터야?',
        '{sem} 개강일이 언제예요?',
        '{sem} {sched} 일정 알려줘',
        '수강정정 기간 알려줘',
        '계절학기 신청은 언제 해요?',
        '중간고사 기간이 언제인가요?',
        '{sem} 학사일정 알려줘',
        '{sched} 일정 좀 알려주세요',
        '{sem} 방학 언제 시작해요?',
        '성적 정정 기간이 언제죠?',
        '{sched} 언제까지예요?',
        '{sem} 종강이 언제예요?',
        '{sched} 신청 마감이 언제야?',
    ],
    3: [  # 식단
        '오늘 학식 뭐 나와요?',
        '{meal} 학식 메뉴 알려줘',
        '{hall} 오늘 메뉴 뭐야?',
        '{hall} {meal} 식단 알려줘',
        '오늘 점심 뭐 나와?',
        '학식 메뉴 좀 알려주세요',
        '{hall} 식단표 보여줘',
        '오늘 저녁 학식 뭐예요?',
        '{meal} 식당 메뉴가 뭐죠?',
        '학생회관 식당 오늘 뭐 나와?',
        '교내 식당 메뉴 알려줘',
    ],
    4: [  # 통학/셔틀 버스
        '{day}에 셔틀버스는 정상 운행하나요?',
        '셔틀버스 시간표 알려줘',
        '통학버스 몇 시에 있어요?',
        '{route} 가는 셔틀 정류장이 어디예요?',
        '{day}에 셔틀버스 운행해요?',
        '{route} 셔틀 노선 알려줘',
        '셔틀버스 첫차가 몇 시예요?',
        '{day} 셔틀버스 다녀?',
        '통학버스 시간표 좀 보여줘',
        '{route} 셔틀 어디서 타요?',
        '막차 셔틀 몇 시예요?',
        '{route}행 셔틀 배차 간격이 어떻게 돼?',
        '{day}에 통학버스 운행 여부 알려줘',
        '{route} 정류장 위치가 어디죠?',
        '셔틀버스 {day} 운행 시간 알려줘',
        '{route}에서 셔틀 타려면 어디로 가요?',
    ],
}

SLOTS = {'hall': DINING_HALLS, 'meal': MEALS, 'dept': DEPTS,
         'major': MAJOR_TERMS, 'sched': SCHED_TERMS, 'sem': SEM,
         'route': ROUTE, 'day': DAY, 'topic': TOPIC}


def fill(template):
    """템플릿의 {slot} 을 무작위 값으로 채움. 슬롯 없으면 그대로."""
    def repl(m):
        key = m.group(1)
        vals = SLOTS.get(key, [''])
        return RNG.choice(vals)
    return re.sub(r'\{(\w+)\}', repl, template)


def crawl_titles(category_ids, n=40):
    """크롤 데이터 제목에서 엔티티 보강(실제 학과/식당명 등)."""
    try:
        d = json.load(open(ALL, encoding='utf-8'))
    except Exception:
        return []
    out = []
    for x in d:
        if x.get('data_category') in category_ids:
            t = (x.get('title') or '').strip()
            if 4 <= len(t) <= 25 and '충남대' not in t:
                out.append(t)
    RNG.shuffle(out)
    return out[:n]


def main():
    # 크롤 제목으로 슬롯 보강(학과명 다양화) — " - 소개" 등 군더더기 제거
    extra = []
    for t in crawl_titles({'F_department', 'department_general'}, 60):
        name = re.split(r'\s*[-–|(\[]', t)[0].strip()
        if re.search(r'(학과|학부|전공|과)$', name) and 3 <= len(name) <= 12:
            extra.append(name)
    SLOTS['dept'] = list(dict.fromkeys(DEPTS + extra))  # 중복제거, 순서유지

    PER_CAT = 220  # 카테고리당 목표 질문 수
    samples = []
    for label, templates in TEMPLATES.items():
        seen = set()
        tries = 0
        while len([s for s in samples if s['label'] == label]) < PER_CAT and tries < PER_CAT * 30:
            tries += 1
            q = fill(RNG.choice(templates)).strip()
            if q and q not in seen:
                seen.add(q)
                samples.append({'question': q, 'label': label})

    # 균형 다운샘플: 카테고리별 최소 개수에 맞춰 편향 방지
    import collections
    by_label = collections.defaultdict(list)
    for s in samples:
        by_label[s['label']].append(s)
    cap = min(len(v) for v in by_label.values())
    balanced = []
    for lab, xs in by_label.items():
        RNG.shuffle(xs)
        balanced.extend(xs[:cap])
    samples = balanced
    RNG.shuffle(samples)
    print(f'균형 다운샘플: 카테고리당 {cap}개')

    # 90/10 분리 (라벨 비율 유지되도록 셔플 후 분리)
    n_val = len(samples) // 10
    valid, train = samples[:n_val], samples[n_val:]

    json.dump(train, open(OUT / 'train.json', 'w', encoding='utf-8'),
              ensure_ascii=False, indent=2)
    json.dump(valid, open(OUT / 'valid.json', 'w', encoding='utf-8'),
              ensure_ascii=False, indent=2)

    import collections
    ctr = collections.Counter(s['label'] for s in samples)
    print(f'합성 완료: train {len(train)} / valid {len(valid)} (총 {len(samples)})')
    names = {0: '졸업요건', 1: '공지', 2: '학사일정', 3: '식단', 4: '셔틀'}
    for k in range(5):
        print(f'  label {k} {names[k]}: {ctr[k]}')
    print(f'→ {OUT/"train.json"} , {OUT/"valid.json"}')
    print('\n샘플 5건:')
    for s in samples[:5]:
        print(f'  [{s["label"]}] {s["question"]}')


if __name__ == '__main__':
    main()
