"""질문유형 분류기(Task1) 학습 데이터 생성 — 템플릿 x 슬롯 조합.

라벨: 졸업요건=0, 학교공지=1, 학사일정=2, 식단=3, 통학/셔틀=4

산출: data/cls/train.json, data/cls/valid.json  (포맷 [{"question": "...", "label": N}, ...])
보존: data/cls/eval_natural.json 은 사람이 직접 쓴 구어체 평가셋이라 생성 대상이 아니다.
      템플릿 밖 일반화 성능을 재는 용도로 그대로 둔다.

라벨 경계 규칙(eval_natural.json 의 사람 라벨과 동일하게 맞춤):
  - "공지 / 공고 / 안내문" 이 들어가면 1 (학사 관련이어도 1이 이긴다)
  - "언제 / 기간 / 며칠 / 마감 / 일정" 은 2
  - 등록금은 "공지"면 1, "납부 기간"이면 2

실행:
    python scripts/build_cls_dataset.py            # 기본 라벨당 600개
    CLS_PER_LABEL=300 python scripts/build_cls_dataset.py
"""
import json
import os
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "cls"

PER_LABEL = int(os.environ.get("CLS_PER_LABEL", "600"))
VALID_RATIO = float(os.environ.get("CLS_VALID_RATIO", "0.1"))
SEED = int(os.environ.get("CLS_SEED", "42"))

LABEL_NAMES = ["졸업요건", "학교공지", "학사일정", "식단", "통학/셔틀"]

# ── 슬롯 어휘 (기존 data/cls/*.json 과 data/test_cls.json 에서 추출한 실제 도메인 어휘) ──
DEPT = [
    "컴퓨터융합학부", "컴퓨터인공지능학부", "전자공학과", "전기공학과", "기계공학부",
    "신소재공학과", "메카트로닉스공학과", "자율운항시스템공학과", "선박해양공학과",
    "식품공학과", "화학과", "수학과", "정보통계학과", "생명시스템과학과",
    "국어국문학과", "독어독문학과", "심리학과", "행정학부", "경제학과", "경영학부",
    "무역학과", "간호학과", "약학과", "농업경제학과", "건축학과", "환경공학과",
]
DEGREE_SCOPE = ["전공", "교양", "일반선택", "전공심화", "복수전공", "부전공", "융합전공"]
GRAD_TOPIC = [
    "졸업학점", "졸업요건", "졸업 사정 기준", "졸업논문 요건", "영어인증 기준",
    "전공 이수학점", "교양 이수학점", "졸업 필수과목",
]
NOTICE_KIND = [
    "공지", "새 공지", "학사 공지", "장학 공지", "근로장학 공지", "등록금 공지",
    "비교과 공지", "취업 공지", "현장실습 공고", "채용설명회 공지", "교내 행사 공지",
]
# 일정 어휘는 두 갈래로 나눈다. "학위수여식 마감이 언제죠?" 같은 어색한 조합을 막기 위해
# 마감/기간을 물을 수 있는 신청류(DEADLINE)와, 날짜만 묻는 행사류(EVENT)를 분리했다.
SCHEDULE_DEADLINE = [
    "수강신청", "수강정정", "수강철회", "재수강 신청", "성적입력", "성적정정",
    "계절학기 신청", "휴학 신청", "복학 신청", "등록금 납부", "졸업신청",
]
SCHEDULE_EVENT = [
    "개강", "종강", "중간고사", "기말고사", "방학", "학위수여식", "오리엔테이션", "축제",
]
SCHEDULE_ITEM = SCHEDULE_DEADLINE + SCHEDULE_EVENT
TERM = ["이번 학기", "다음 학기", "이번학기", "2학기", "1학기", "겨울 계절학기", "여름 계절학기", ""]
RESTAURANT = [
    "학생회관 식당", "기숙사 식당", "생활관식당", "교직원식당", "백마교양관 식당",
    "전망 좋은 식당", "푸드코트", "구내식당", "학식",
]
WHEN = ["오늘", "내일", "이번주", "다음주", "주말", "월요일", "화요일", "수요일", "목요일", "금요일", ""]
MEAL = ["아침", "점심", "저녁", ""]
SHUTTLE_DEST = [
    "공대행", "궁동행", "정문행", "기숙사행", "대덕캠퍼스행", "보운캠퍼스행",
    "대전역행", "서대전행", "유성행", "대학로행", "순환행", "월평역행",
    "유성온천역행", "충남대병원행", "농대행", "예술대행",
]
SHUTTLE_TOPIC = [
    "배차 간격", "노선", "시간표", "첫차 시간", "막차 시간", "정류장 위치",
    "운행 여부", "요금", "탑승 위치", "운행 시간",
]

# ── 템플릿: {slot} 자리를 위 어휘로 채운다. 어미를 섞어 문체 다양성 확보 ──
TEMPLATES = {
    0: [
        "{dept} {grad} 알려줘",
        "{dept} {grad}이 어떻게 되나요?",
        "{dept} 졸업하려면 뭐가 필요해?",
        "{dept} 졸업학점이 몇 점이에요?",
        "{scope} 몇 학점 들어야 졸업해?",
        "{scope} 이수 학점 어떻게 채워요?",
        "{scope} 이수 기준 좀 알려주세요",
        "{grad} 정리된 자료 있나요?",
        "{term} 졸업하려면 학점 얼마나 필요해?",
        "졸업 가능한지 어디서 확인하지?",
        "졸업까지 남은 학점 어떻게 확인해요?",
        "{scope} 하면 졸업이 늦어지나요?",
        "졸업논문 꼭 써야 하나요?",
        "졸업 요건에 어학 점수 필요해요?",
        "{dept} {scope} 인정 학점이 몇이야?",
    ],
    1: [
        "{dept} {notice} 알려줘",
        "{dept} {notice} 있나요?",
        "{dept} {notice} 어디서 봐?",
        "{notice} 올라온 거 있어요?",
        "{notice} 어디서 확인해요?",
        "{term} 올라온 {notice} 알려주세요",
        "학교 홈페이지 {notice} 어디 있어?",
        "{dept} 사무실에서 올린 안내문 어디서 봐요?",
        "최근 {notice} 뭐 떴어?",
        "{notice} 새로 뜬 거 알려줘",
        "총학생회 공지 보려면 어디로 가요?",
        "교내 안내문 어디서 확인하나요?",
    ],
    2: [
        # 신청류: 기간/마감을 물어도 자연스럽다
        "{term} {deadline} 일정 알려줘",
        "{deadline} 언제부터야?",
        "{deadline} 기간이 언제인가요?",
        "{deadline} 며칠까지 할 수 있어?",
        "{deadline} 마감이 언제죠?",
        "{term} {deadline} 기간 알려주세요",
        "{deadline} 지났나요?",
        "{term} {deadline} 기간 며칠이야?",
        "{deadline} 어디서 신청해요?",
        "{term} {deadline} 시작일 알려줘",
        # 행사류: 날짜만 묻는다
        "{term} {event} 언제예요?",
        "{term} {event}일이 언제인가요?",
        "{event} 언제 시작해요?",
        "{term} {event} 날짜 알려줘",
        "{event} 일정 좀 알려주세요",
        # 공통
        "{term} 학사일정 알려줘",
        "학사일정표 어디서 봐요?",
    ],
    3: [
        "{rest} {when} 식단 알려줘",
        "{when} {rest} 메뉴 뭐예요?",
        "{when} {meal} 학식 뭐 나와?",
        "{rest} {when} {meal} 메뉴 알려주세요",
        "{when} 학식 뭐 줘?",
        "{rest} 메뉴 좀 알려줘",
        "{when} 식단표 어디서 봐요?",
        "{rest} 오늘 뭐 파나요?",
        "{when} {meal} 식단 알려줘",
        "{rest} 운영하나요?",
        "학식 가격이 얼마예요?",
        "{rest} {when} 식단 뭔지 알려줄래?",
    ],
    4: [
        "{dest} 셔틀 {stopic} 어떻게 돼?",
        "{dest} 셔틀 {stopic} 알려줘",
        "{when} {dest} 셔틀 {stopic} 알려줘",
        "{when} {dest} 통학버스 {stopic} 어떻게 되나요?",
        "{dest} 셔틀 {stopic} 좀 알려주세요",
        "셔틀버스 {stopic} 알려주세요",
        "통학버스 {stopic} 어디서 봐요?",
        "{when} 셔틀버스 운행하나요?",
        "{when}도 셔틀 다녀?",
        "{dest} 셔틀 어디서 타요?",
        "셔틀 {stopic} 좀 알려줘",
        "교내 순환버스 {stopic} 어떻게 되나요?",
        "방학 때 셔틀 운행해요?",
        "시험기간에 통학버스 다니나요?",
        "{dest} 버스 {stopic} 알려줘",
    ],
}

SLOT_POOLS = {
    "dept": DEPT,
    "scope": DEGREE_SCOPE,
    "grad": GRAD_TOPIC,
    "notice": NOTICE_KIND,
    "sched": SCHEDULE_ITEM,
    "deadline": SCHEDULE_DEADLINE,
    "event": SCHEDULE_EVENT,
    "term": TERM,
    "rest": RESTAURANT,
    "when": WHEN,
    "meal": MEAL,
    "dest": SHUTTLE_DEST,
    "stopic": SHUTTLE_TOPIC,
}


def normalize(text):
    """빈 슬롯이 만든 이중 공백과, 슬롯 결합으로 생긴 중복 어절을 정리한다.

    예: "{deadline} 신청 기간" + deadline="수강신청" → "수강신청 신청 기간"
        → 인접 중복 어절을 접어서 "수강신청 기간" 으로 만든다.
    """
    words = text.split()
    out = []
    for w in words:
        # 바로 앞 어절과 같거나, 앞 어절이 이 어절로 끝나면(수강신청 + 신청) 건너뛴다.
        if out and (out[-1] == w or out[-1].endswith(w)):
            continue
        out.append(w)
    return " ".join(out)


def generate_for_label(label, rng, target):
    """템플릿 x 슬롯을 무작위 조합해 중복 없는 질문을 target 개 만든다."""
    templates = TEMPLATES[label]
    seen = set()
    out = []
    # 조합 공간이 target 보다 작을 수 있으므로 시도 횟수에 상한을 둔다.
    for _ in range(target * 200):
        if len(out) >= target:
            break
        filled = rng.choice(templates)
        for slot, pool in SLOT_POOLS.items():
            token = "{" + slot + "}"
            if token in filled:
                filled = filled.replace(token, rng.choice(pool))
        question = normalize(filled)
        if question and question not in seen:
            seen.add(question)
            out.append(question)
    return out


def main():
    rng = random.Random(SEED)
    train_rows = []
    valid_rows = []

    print("[build] per_label=%d  valid_ratio=%s  seed=%d" % (PER_LABEL, VALID_RATIO, SEED))
    for label in range(5):
        questions = generate_for_label(label, rng, PER_LABEL)
        if len(questions) < PER_LABEL:
            print("  ! label %d: 조합 공간 부족 %d/%d" % (label, len(questions), PER_LABEL))
        rng.shuffle(questions)
        n_valid = max(1, int(len(questions) * VALID_RATIO))
        # 문자열 단위로 분리 — valid 질문은 train 에 등장하지 않는다.
        valid_rows += [{"question": q, "label": label} for q in questions[:n_valid]]
        train_rows += [{"question": q, "label": label} for q in questions[n_valid:]]
        print("  label %d %-8s train=%4d  valid=%3d"
              % (label, LABEL_NAMES[label], len(questions) - n_valid, n_valid))

    rng.shuffle(train_rows)
    rng.shuffle(valid_rows)

    # 누수 검사: valid 질문이 train 에 하나라도 있으면 제거한다.
    train_set = {r["question"] for r in train_rows}
    leaked = [r["question"] for r in valid_rows if r["question"] in train_set]
    if leaked:
        print("[build] 누수 %d건 발견 → valid 에서 제거" % len(leaked), file=sys.stderr)
        valid_rows = [r for r in valid_rows if r["question"] not in train_set]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, rows in (("train.json", train_rows), ("valid.json", valid_rows)):
        path = OUT_DIR / name
        with open(path, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)
        print("[build] %s  n=%d" % (path, len(rows)))

    print("[build] 누수 0건 확인 (train %d / valid %d)" % (len(train_rows), len(valid_rows)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
