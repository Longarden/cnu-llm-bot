"""커버리지 보강용 staging 생성기.

평가에서 '자료 없음'으로 거절된 주제들의 실제 정보를 충남대 공식 페이지에서
수집해 data/crawled_staging/coverage_new.json 으로 저장한다.

원칙: 페이지에서 trafilatura로 실제 추출한 본문만 사용. 사실을 지어내지 않는다.
추출 실패하거나 본문에 기대 키워드가 없으면 건너뛰고 '수집실패'로 리포트한다.
"""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

# 프로젝트 루트 경로 보정
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from crawler_pipeline.body_extractor import fetch_html, extract_main_text  # noqa: E402

OUT_PATH = ROOT / "data" / "crawled_staging" / "coverage_new.json"

NOW = datetime.now()
NOW_ISO = NOW.isoformat()


def vu(days: int) -> str:
    return (NOW + timedelta(days=days)).isoformat()


# (topic, url, category, title, valid_days, must_contain[any])
# must_contain: 본문에 이 키워드들 중 하나라도 있어야 채택(nav-only/오추출 방지)
TARGETS = [
    # ----- 도서관 (A_library) -----
    ("도서관 휴관일/개관시간",
     "https://library.cnu.ac.kr/webcontent/info/48", "A_library",
     "충남대 도서관 휴관일 및 개관시간 안내", 60,
     ["휴실", "공휴일", "개관", "운영시간", "방학중"]),
    ("도서관 대출/연장/예약 규정",
     "https://library.cnu.ac.kr/webcontent/info/325", "A_library",
     "충남대 도서관 자료 대출/연장/예약 안내", 60,
     ["대출", "연장", "예약"]),
    ("도서관 신분별 대출 권수/기간(학부생)",
     "https://library.cnu.ac.kr/webcontent/info/330", "A_library",
     "충남대 도서관 학부생 대출 권수/기간 안내", 60,
     ["대출가능권수", "10책", "반납지연", "희망도서"]),
    ("도서관 신분별 대출 권수/기간(대학원생)",
     "https://library.cnu.ac.kr/webcontent/info/331", "A_library",
     "충남대 도서관 대학원생 대출 권수/기간 안내", 60,
     ["대출가능권수", "20책", "반납지연"]),
    ("도서관 자료 대출 권수/기간 종합표",
     "https://library.cnu.ac.kr/webcontent/info/335", "A_library",
     "충남대 도서관 신분별 대출책수/대출기간/연체일수 표", 60,
     ["대출책수", "대출기간", "연체", "학부생"]),
    ("도서관 열람실/좌석/노트북 이용",
     "https://library.cnu.ac.kr/webcontent/info/312", "A_library",
     "충남대 도서관 열람실 운영시간/좌석 배정/노트북 사용 안내", 60,
     ["열람실", "좌석", "노트북", "지정석"]),
    ("도서관 사물함 신청",
     "https://library.cnu.ac.kr/webcontent/info/346", "A_library",
     "충남대 도서관 사물함 신청/이용 안내", 60,
     ["사물함", "신청기간", "추첨", "배정"]),
    ("도서관 그룹스터디룸/층별안내",
     "https://library.cnu.ac.kr/webcontent/info/326", "A_library",
     "충남대 도서관 층별안내(그룹스터디룸/미디어제작실 등)", 60,
     ["그룹스터디룸", "미디어", "스터디", "운영시간"]),
    ("도서관 프린터/복사/출력/스캔 위치",
     "https://library.cnu.ac.kr/webcontent/info/337", "A_library",
     "충남대 도서관 복사/출력/스캔 위치 및 이용시간", 60,
     ["복사", "출력", "스캔", "프린터", "연속간행물실"]),
    ("도서관 미디어존",
     "https://library.cnu.ac.kr/webcontent/info/321", "A_library",
     "충남대 도서관 미디어존 이용 안내", 60,
     ["미디어", "VR", "검색용", "이용시간"]),
    ("도서관 자주 묻는 질문(FAQ)",
     "https://library.cnu.ac.kr/faqlib/faq?code=all", "A_library",
     "충남대 도서관 자주 묻는 질문(그룹스터디룸/사물함/노트북/복사 등)", 30,
     ["그룹스터디룸", "사물함", "노트북", "복사", "외부인"]),

    # ----- 학사 (B_academic) -----
    ("학사일정(학사일정/개강·종강·시험·조기졸업신청 등)",
     "https://plus.cnu.ac.kr/_prog/academic_calendar/?site_dvs_cd=kr&menu_dvs_cd=05020101",
     "B_academic",
     "충남대 2026학년도 학사일정(개강일/수업일수/조기졸업신청/방학 등)", 90,
     ["개강일", "수업일수", "성적발표", "방학"]),
    ("학사: 휴학/복학(일반휴학 최대학기 등)",
     "https://plus.cnu.ac.kr/html/hub/affairs/affairs_020201.html", "B_academic",
     "충남대 휴학·복학 안내(일반휴학 가능기간/최대학기/복학)", 90,
     ["휴학", "복학", "학기", "복학"]),
    ("학사: 전과 자격",
     "https://plus.cnu.ac.kr/html/hub/affairs/affairs_020202.html", "B_academic",
     "충남대 전과 자격 및 절차(평균평점 2.5 이상, 2학년 이상)", 90,
     ["전과", "평균평점", "2학년", "취득학점"]),
    ("학사: 재입학",
     "https://plus.cnu.ac.kr/html/hub/affairs/affairs_020203.html", "B_academic",
     "충남대 재입학 자격 및 절차", 90,
     ["재입학", "성적경고", "제적"]),
    ("학사: 제적/자퇴(학사경고 제적 기준)",
     "https://plus.cnu.ac.kr/html/hub/affairs/affairs_020204.html", "B_academic",
     "충남대 제적/자퇴 사유(연속 3회 성적경고 제적 등)", 90,
     ["제적", "성적경고", "자퇴", "재학연한"]),
    ("학사: 수업/재학연한",
     "https://plus.cnu.ac.kr/html/hub/affairs/affairs_020205.html", "B_academic",
     "충남대 수업연한 및 재학연한 안내", 90,
     ["수업연한", "재학연한", "4년"]),
    ("학사: 졸업 요건/조기졸업/졸업유예(학사학위취득유예)",
     "https://plus.cnu.ac.kr/html/hub/affairs/affairs_020206.html", "B_academic",
     "충남대 졸업 요건/조기졸업/학사학위취득유예(졸업유예) 안내", 90,
     ["졸업", "조기졸업", "학사학위취득유예", "졸업소요학점"]),
    ("학사: 성적/학사경고 기준/재이수(재수강) 성적상한제",
     "https://plus.cnu.ac.kr/html/hub/affairs/affairs_020302.html", "B_academic",
     "충남대 성적 평가/학사경고 기준(평점 1.75 미만)/재이수 성적상한제", 90,
     ["평점", "성적", "1.75", "재이수"]),
    ("학사: 계절학기",
     "https://plus.cnu.ac.kr/html/hub/affairs/affairs_020303.html", "B_academic",
     "충남대 계절학기 운영/신청학점/재이수 안내", 90,
     ["계절학기", "재이수", "수강신청", "6학점"]),
    ("학사: 학점교류 및 최대 수강(이수기준)학점",
     "https://plus.cnu.ac.kr/html/hub/affairs/affairs_020304.html", "B_academic",
     "충남대 학점교류 및 학기당 이수기준(최대 수강)학점 안내", 90,
     ["이수 기준 학점", "이수기준", "학점교류", "초과 이수"]),
    ("학사: 영어능력인정 및 대학영어 재이수",
     "https://plus.cnu.ac.kr/html/hub/affairs/affairs_020305.html", "B_academic",
     "충남대 영어능력 학점인정 기준 및 대학영어 재이수 안내", 90,
     ["영어능력", "TOEIC", "재이수", "면제"]),
    ("학사: 교직과정 이수",
     "https://plus.cnu.ac.kr/html/hub/academic/academic_010209.html", "B_academic",
     "충남대 교직과정 이수 신청/선발/학점 요건", 90,
     ["교직과정", "교직", "정교사", "전공과목"]),

    # ----- 셔틀 (A_shuttle) -----
    ("셔틀: 정류장/막차/운행 안하는 날/시간표",
     "https://plus.cnu.ac.kr/html/kr/sub05/sub05_050403.html", "A_shuttle",
     "충남대 셔틀버스 운행시간표/정류장/막차/미운영일 안내", 90,
     ["셔틀", "운영기준", "정류장", "막차", "운행"]),

    # ----- 기숙사 식당 (G_dormitory) -----
    ("기숙사 식당 운영시간",
     "https://dorm.cnu.ac.kr/html/kr/sub04/sub04_040301.html", "G_dormitory",
     "충남대 기숙사(생활관) 식당 운영시간(아침/점심/저녁)", 60,
     ["아침", "점심", "저녁", "식단"]),
]


def main():
    docs = []
    ok, fail = [], []
    for topic, url, cat, title, days, must in TARGETS:
        try:
            html = fetch_html(url, timeout=25)
            txt = extract_main_text(html, min_len=40)
        except Exception as e:
            fail.append((topic, url, f"fetch_err:{type(e).__name__}"))
            continue
        if not txt:
            fail.append((topic, url, "extract_none"))
            continue
        if must and not any(k in txt for k in must):
            fail.append((topic, url, "no_keyword"))
            continue
        doc = {
            "source_url": url,
            "data_category": cat,
            "last_crawled_at": NOW_ISO,
            "valid_until": vu(days),
            "freshness_tier": "semi_static",
            "original_text": txt,
            "title": title,
            "content": txt,
            "date": NOW.strftime("%Y-%m-%d"),
        }
        docs.append(doc)
        ok.append((topic, url, len(txt)))

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(docs, f, ensure_ascii=False, indent=2)

    # 리포트
    print("=" * 60)
    print(f"총 문서 수: {len(docs)}  (성공 {len(ok)} / 실패 {len(fail)})")
    print(f"저장 경로: {OUT_PATH}")
    print("-" * 60)
    print("[성공]")
    for t, u, n in ok:
        print(f"  OK  {t}  ({n}자)  {u}")
    print("-" * 60)
    print("[수집실패]")
    if not fail:
        print("  (없음)")
    for t, u, why in fail:
        print(f"  FAIL [{why}]  {t}  {u}")


if __name__ == "__main__":
    main()
