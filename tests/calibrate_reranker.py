"""CRAG 밴드 보정용: 도메인 안/밖 질문의 리랭커 점수(0~1) 분포 측정.
이 숫자를 보고 Correct/Ambiguous/Incorrect 경계를 정한다(감 아니라 근거로).
LLM 없음. 실행: python tests/calibrate_reranker.py  (miniconda python, RERANK=1)"""
import sys, io, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
os.environ["RERANK"] = "1"

from retrieval import hybrid_retriever as hr
from retrieval.reranker import rerank

IN_DOMAIN = [
    # 학사
    "졸업하려면 몇 학점 필요해?", "수강신청 정정 기간 언제야?", "휴학 신청 어떻게 해?",
    "재수강 규정 알려줘", "계절학기 등록금 얼마야?", "전과 신청 자격이 뭐야?",
    # 장학/행정
    "국가장학금 신청 어떻게 해?", "근로장학생 어떻게 신청해?", "재학증명서 발급 방법",
    "성적증명서 영문 발급 돼?", "등록금 분할납부 돼?",
    # 학과(컴공)
    "컴퓨터인공지능학부 어디 있어?", "컴공 졸업요건 알려줘", "컴공 교수님 연구실 어디야?",
    # 취업
    "백마인턴십이 뭐야?", "현장실습 학점 인정 돼?", "취업지원센터 어디 있어?",
    # 시설/생활/도서관/셔틀/학식
    "도서관 운영시간 알려줘", "기숙사 입사 신청 어떻게 해?", "셔틀버스 시간표 알려줘",
    "오늘 학식 메뉴 뭐야?", "기숙사 비용 얼마야?",
    # 공지(본문 추가된 것 확인용)
    "SW/AI 프로젝트 페어 접수 어떻게 해?", "외국인 근로자 자녀 장학생 선발 안내",
]
OUT_DOMAIN = [
    # 명백한 도메인 밖
    "오늘 날씨 어때?", "비트코인 시세 알려줘", "서울대 입학 어떻게 해?",
    "맛있는 김치찌개 레시피", "아이폰 최신 모델 뭐야?", "삼성전자 주가 얼마야?",
    "한국 대통령 누구야?", "월드컵 언제 해?",
    # 키워드필터 못 잡는 일상 질문 (진짜 시험대)
    "오늘 저녁 뭐 먹지?", "주말에 어디 놀러갈까?", "넷플릭스 추천 영화",
    "여자친구 선물 뭐가 좋을까?", "다이어트 어떻게 해?", "기분이 우울해",
    # 대학 관련이지만 우리 데이터엔 없는 것 (경계 케이스)
    "충남대 야구부 경기 일정", "충남대 총장 누구야?", "충남대 의대 입결 알려줘",
]

hr.init_bm25_from_db()
print("=== 도메인 안 (정답 있어야 -> 점수 높길 기대) ===")
in_scores = []
for q in IN_DOMAIN:
    docs = hr.retrieve(q, n_results=10)
    top = rerank(q, docs, top_k=1)
    sc = top[0].get("rerank_score", 0.0) if top else 0.0
    in_scores.append(sc)
    txt = (top[0].get("original_text", "") or "")[:35].replace("\n", " ") if top else ""
    print(f"  {sc:.3f} | {q}  -> {txt}")

print("\n=== 도메인 밖 (자료 없어야 -> 점수 낮길 기대) ===")
out_scores = []
for q in OUT_DOMAIN:
    docs = hr.retrieve(q, n_results=10)
    top = rerank(q, docs, top_k=1)
    sc = top[0].get("rerank_score", 0.0) if top else 0.0
    out_scores.append(sc)
    txt = (top[0].get("original_text", "") or "")[:35].replace("\n", " ") if top else ""
    print(f"  {sc:.3f} | {q}  -> {txt}")

print("\n=== 요약 ===")
print(f"도메인 안:  최소 {min(in_scores):.3f}  평균 {sum(in_scores)/len(in_scores):.3f}  최대 {max(in_scores):.3f}")
print(f"도메인 밖:  최소 {min(out_scores):.3f}  평균 {sum(out_scores)/len(out_scores):.3f}  최대 {max(out_scores):.3f}")
gap = min(in_scores) - max(out_scores)
print(f"분리 마진(안 최소 - 밖 최대): {gap:.3f}  {'<- 잘 갈림' if gap > 0 else '<- 겹침, 밴드 신중히'}")
print("이 숫자로 Correct/Ambiguous/Incorrect 경계를 정한다.")
