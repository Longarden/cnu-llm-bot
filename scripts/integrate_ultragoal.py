"""울트라골 일괄 통합: 크롤/첨부 staging + 이미지 OCR(메인 vision 판독) → all_dedup.json.

한 번에 통합해 reindex 1회로 끝나게 한다. 품질게이트(9키/U+FFFD/길이) + source_url 중복제거 +
computer 첨부의 '교내 일반소식' 제목 보정 포함.
실행: python scripts/integrate_ultragoal.py
"""
import json, os, glob
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALL = os.path.join(ROOT, "data", "crawled", "all_dedup.json")
STG = os.path.join(ROOT, "data", "crawled_staging")
NOW = datetime.utcnow().isoformat()
REQ = ["source_url", "data_category", "last_crawled_at", "valid_until",
       "freshness_tier", "original_text", "title", "content", "date"]

STAGING_FILES = [
    "academic_calendar.json",
    "ub_grad_rules.json",
    "extra_notices.json",
    "ub_attach_plus.json",
    "ub_attach_computer.json",
]


def doc(title, text, url, cat, fresh="time_sensitive", valid="2026-12-31T00:00:00", date="2026-06-02"):
    return {"source_url": url, "data_category": cat, "last_crawled_at": NOW,
            "valid_until": valid, "freshness_tier": fresh, "original_text": text,
            "title": title, "content": text, "date": date}


# ── 이미지 OCR 레코드 (메인이 vision으로 직접 판독해 전사) ──
PLUS = "https://plus.cnu.ac.kr/_prog/_board/?code=sub07_0701&mode=list"
CMP = "https://computer.cnu.ac.kr/computer/notice/notice.do"
OCR = [
    doc("충남대 외국어성적(영어능력인증) 신청 방법",
        "통합정보시스템 외국어성적신청 안내(학생): 영어능력인정 성적 등록(예정)일은 신청 학기 성적발표일 이후입니다. "
        "외국어구분은 공인어학시험(TOEIC, TOEFL, NEW TEPS, TOEIC Speaking, OPIc, IELTS, G-TELP, 본교 모의토익 등)에서 선택합니다. "
        "취득점수는 숫자만 입력, 취득일자는 시험일 기재, 첨부파일은 공인영어성적표(PDF/한글/이미지) 업로드. "
        "업로드한 공인영어성적표 원본은 소속 학과에 반드시 제출해야 합니다. "
        "OPIc 환산: 2013학년도 이전 입학자 IM2->2, IM3->3, IH->4, AL->5 / 2014학년도 이후 입학자 IM3->3, IH->4, AL->5.",
        "https://computer.cnu.ac.kr/computer/notice/bachelor.do", "B_academic", "static", "2026-12-31T00:00:00"),
    doc("천원의 저녁밥 (2026 1학기 기말고사 응원, 제2학생회관)",
        "총장님의 기말고사 응원 '천원의 저녁밥' 행사입니다. 일시: 2026년 6월 8일(월)~6월 11일(목) 17:30~19:00. "
        "장소: 제2학생회관 학생식당(대덕/보운/세종 캠퍼스 운영). 가격 1,000원. "
        "메뉴 - 6/8(월) 함박하이라이스·우동국물·배추김치 / 6/9(화) 밥·소고기깻잎국·요거트티·김치 / "
        "6/10(수) 치즈제육덮밥·유부된장국·단무지 / 6/11(목) 닭갈비볶음밥·얼큰어묵국·요거트티·김치.",
        "https://plus.cnu.ac.kr/_prog/_board/?code=sub07_0701&mode=V&no=2513451", "A_dining", "time_sensitive", "2026-06-12T00:00:00", "2026-06-08"),
    doc("국가보안기술연구소(NSR) 채용설명회 및 상담회",
        "국가보안기술연구소(NSR) 채용설명회 및 상담회 안내. 일시: 2026년 6월 2일(화), 채용설명회 14:00~15:00, 채용상담회 15:00~17:00. "
        "장소: 인재개발원(E5) 2층(설명회 5층 시너지실/상담회 2층 라운지). 대상: 보안/연구 분야 취업 희망 학생. "
        "신청기간: ~2026년 6월 1일(월) 23:59. 문의: 인재개발원 042-821-6954.",
        "https://plus.cnu.ac.kr/_prog/_board/?code=sub07_0702&mode=V&no=2513402", "K_notices", "time_sensitive", "2026-06-03T00:00:00", "2026-06-02"),
    doc("CNU 진로·취업 JOB지 (2026년 6월 프로그램 일정)",
        "충남대 인재개발원(대학일자리플러스센터) 2026년 6월 진로·취업 프로그램 월간 일정. "
        "지능형 에이전트(AI Agent) 개발 실전특강(~8.2), 취업실루 진단컨설팅·취업나침반, 지역동행 직무업(대전 Co-work)·진로콘텐츠 프로그램, "
        "면접·자기소개서 컨설팅, 선배의 커리어 리얼토크 모임(~7.5) 등. 상세 일정·신청은 충남대 학사지원시스템 및 SNS 확인.",
        "https://plus.cnu.ac.kr/_prog/_board/?code=sub07_0702&mode=V&no=2513450", "K_notices", "time_sensitive", "2026-06-30T00:00:00", "2026-06-02"),
    doc("경영지원직무 실전 취업 완전대비 프로그램",
        "인재개발원 '경영지원직무 실전 취업 완전대비' 비교과 프로그램. 운영일시: 2026년 6월 22일(월) 09:30~17:00. "
        "장소: 인재개발원(E5) 2층 시너지실. 모집대상: 충남대 재학생 및 졸업생 선착순 30명(인문사회경상계열 환영, 공기업 준비 이공계열도 환영). "
        "내용: 경영지원 직무 맞춤형 자기소개서 스킬, 기업 유형별 현직자 멘토링, 면접 준비 특강, 모의면접. "
        "혜택: 재학생 꿈모아마일리지 적립. 신청: CNU With U+(학사지원시스템) - 개인비교과 '경영지원' 검색.",
        "https://plus.cnu.ac.kr/_prog/_board/?code=sub07_0702&mode=V&no=2513455", "K_notices", "time_sensitive", "2026-06-23T00:00:00", "2026-06-22"),
    doc("창업 K-startup 특강 2차 (컴퓨터인공지능학부)",
        "충남대 정보보호 특성화대학지원사업 '창업 K-startup 특강 2차'. 일시: 2026년 6월 4일(목) 12:00~13:00. 장소: 공대 5호관 410호. "
        "대상: 컴퓨터인공지능학부 학부생, 정보보호 특성화대학지원사업 참여학생, 창업에 관심 있는 누구나. "
        "연사: 이로운앤컴퍼니(Eroun&Co) 윤두식 대표(충남대 컴퓨터공학과 졸업 선배), 생성형 AI 보안·블록체인·랜섬웨어 대응 전문가. "
        "주제: 'Claude Mythos 이후의 보안, 무엇이 끝나고 무엇이 시작되는가'. 사전신청자 샌드위치 도시락 제공. 문의: 042-821-8909.",
        "https://computer.cnu.ac.kr/computer/notice/project.do?mode=view&articleNo=586677", "K_notices", "time_sensitive", "2026-06-05T00:00:00", "2026-06-04"),
    doc("Claude for Everyone Daejeon 행사 (충남대 김정규홀)",
        "Daejeon | Claude for Everyone 행사. 일시: 2026년 5월 6일(수) 14:00~18:00. 장소: 충남대학교 김정규홀. "
        "주최: 충남대 소프트웨어중심대학사업단·AI인재양성부트캠프사업단·컴퓨터인공지능학부. 참석신청 Luma 페이지.",
        "https://computer.cnu.ac.kr/computer/notice/project.do?mode=view&articleNo=585780", "K_notices", "time_sensitive", "2026-05-07T00:00:00", "2026-05-06"),
]


def fix_title(r):
    """computer 첨부의 '교내 일반소식' 등 약한 제목을 본문 첫 의미 줄로 보정."""
    t = (r.get("title", "") or "").strip()
    if t in ("교내 일반소식", "교내일반소식", "", "공지사항") or len(t) < 4:
        body = (r.get("original_text", "") or "").replace("|", " ").strip()
        first = next((ln.strip() for ln in body.split("\n") if len(ln.strip()) >= 6), body[:40])
        r["title"] = first[:60]
    return r


def valid(r):
    if not all(k in r for k in REQ):
        return False
    blob = (r.get("original_text", "") or "") + (r.get("title", "") or "")
    if "�" in blob:
        return False
    return len(r.get("original_text", "").strip()) >= 20


# ── 통합 ──
dd = json.load(open(ALL, encoding="utf-8"))
print(f"기존 all_dedup: {len(dd)}건")

new_records = list(OCR)
for f in STAGING_FILES:
    p = os.path.join(STG, f)
    if not os.path.exists(p):
        print(f"  (없음, 스킵) {f}")
        continue
    recs = json.load(open(p, encoding="utf-8"))
    recs = [fix_title(r) for r in recs]
    recs = [r for r in recs if valid(r)]
    print(f"  + {f}: {len(recs)}건")
    new_records.extend(recs)

print(f"신규 후보(OCR {len(OCR)} 포함): {len(new_records)}건")

# source_url 중복: 신규로 교체(기존 동일 URL 제거)
new_urls = set(r.get("source_url", "") for r in new_records if r.get("source_url"))
kept = [r for r in dd if r.get("source_url", "") not in new_urls]
merged = kept + new_records
print(f"기존에서 URL중복 제거: {len(dd) - len(kept)}건")

bad = sum(1 for r in merged if "�" in (r.get("original_text", "") + r.get("title", "")))
json.dump(merged, open(ALL, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"=== 완료: all_dedup {len(dd)} -> {len(merged)}건 (U+FFFD {bad}) ===")

from collections import Counter
print("카테고리 분포:", dict(Counter(r.get("data_category", "") for r in merged)))
