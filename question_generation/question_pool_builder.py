# 충남대 RAG 챗봇 - 질문 풀 생성기
# Claude Sonnet API 로 12개 카테고리 × 서브카테고리별 질문 생성
# HuggingFace datasets 라이브러리 사용 금지

import os
import json
import time
from pathlib import Path
from typing import List, Dict

import anthropic

# 12개 카테고리 × 서브카테고리 노드 정의 (약 80개 노드)
CATEGORY_NODES: List[Dict] = [
    # A. 시간성 (학식/도서관/셔틀)
    {"category_id": "A", "category_name": "시간성", "subcategory": "학식 메뉴 및 운영시간"},
    {"category_id": "A", "category_name": "시간성", "subcategory": "도서관 운영시간 및 좌석"},
    {"category_id": "A", "category_name": "시간성", "subcategory": "셔틀버스 시간표"},
    {"category_id": "A", "category_name": "시간성", "subcategory": "오늘/내일 일정 조회"},
    {"category_id": "A", "category_name": "시간성", "subcategory": "주간 운영 변경 공지"},
    # B. 학사 (수강/졸업/일정)
    {"category_id": "B", "category_name": "학사", "subcategory": "수강신청 방법 및 일정"},
    {"category_id": "B", "category_name": "학사", "subcategory": "졸업 요건 및 절차"},
    {"category_id": "B", "category_name": "학사", "subcategory": "학사 일정 (시험/방학/개강)"},
    {"category_id": "B", "category_name": "학사", "subcategory": "성적 처리 및 이의신청"},
    {"category_id": "B", "category_name": "학사", "subcategory": "휴학/복학 절차"},
    {"category_id": "B", "category_name": "학사", "subcategory": "전과/복수전공 신청"},
    {"category_id": "B", "category_name": "학사", "subcategory": "학점 인정 및 교환학점"},
    {"category_id": "B", "category_name": "학사", "subcategory": "학사경고 및 제적 기준"},
    # C. 행정/증명서
    {"category_id": "C", "category_name": "행정", "subcategory": "재학증명서 발급 방법"},
    {"category_id": "C", "category_name": "행정", "subcategory": "성적증명서 발급"},
    {"category_id": "C", "category_name": "행정", "subcategory": "졸업증명서 발급"},
    {"category_id": "C", "category_name": "행정", "subcategory": "등록금 납부 및 환불"},
    {"category_id": "C", "category_name": "행정", "subcategory": "학생증 발급 및 분실"},
    {"category_id": "C", "category_name": "행정", "subcategory": "각종 신청서 제출"},
    # D. 장학/지원
    {"category_id": "D", "category_name": "장학", "subcategory": "교내 장학금 종류 및 신청"},
    {"category_id": "D", "category_name": "장학", "subcategory": "국가장학금 신청 방법"},
    {"category_id": "D", "category_name": "장학", "subcategory": "근로장학금 신청"},
    {"category_id": "D", "category_name": "장학", "subcategory": "긴급생활비 지원"},
    {"category_id": "D", "category_name": "장학", "subcategory": "장학금 수혜 조건"},
    # E. 취업/진로
    {"category_id": "E", "category_name": "취업", "subcategory": "취업지원센터 서비스"},
    {"category_id": "E", "category_name": "취업", "subcategory": "채용 공고 및 인턴십"},
    {"category_id": "E", "category_name": "취업", "subcategory": "이력서/자소서 첨삭"},
    {"category_id": "E", "category_name": "취업", "subcategory": "취업 특강 및 멘토링"},
    {"category_id": "E", "category_name": "취업", "subcategory": "창업 지원 프로그램"},
    # F. 학과 정보
    {"category_id": "F", "category_name": "학과", "subcategory": "컴퓨터공학과 교과과정"},
    {"category_id": "F", "category_name": "학과", "subcategory": "전자공학과 정보"},
    {"category_id": "F", "category_name": "학과", "subcategory": "경영학과 정보"},
    {"category_id": "F", "category_name": "학과", "subcategory": "의과대학 정보"},
    {"category_id": "F", "category_name": "학과", "subcategory": "사범대학 정보"},
    {"category_id": "F", "category_name": "학과", "subcategory": "교수 연구실 위치 및 연락처"},
    {"category_id": "F", "category_name": "학과", "subcategory": "대학원 입학 정보"},
    {"category_id": "F", "category_name": "학과", "subcategory": "학과 사무실 연락처"},
    # G. 학생 생활
    {"category_id": "G", "category_name": "학생생활", "subcategory": "기숙사 신청 및 입사"},
    {"category_id": "G", "category_name": "학생생활", "subcategory": "기숙사 규정 및 생활"},
    {"category_id": "G", "category_name": "학생생활", "subcategory": "동아리 신청 및 활동"},
    {"category_id": "G", "category_name": "학생생활", "subcategory": "학생 상담 서비스"},
    {"category_id": "G", "category_name": "학생생활", "subcategory": "보건소 이용 방법"},
    # H. 캠퍼스 시설
    {"category_id": "H", "category_name": "시설", "subcategory": "강의실 및 건물 위치"},
    {"category_id": "H", "category_name": "시설", "subcategory": "편의시설 (ATM, 카페, 편의점)"},
    {"category_id": "H", "category_name": "시설", "subcategory": "주차장 이용"},
    {"category_id": "H", "category_name": "시설", "subcategory": "체육시설 예약"},
    {"category_id": "H", "category_name": "시설", "subcategory": "강의실/회의실 예약"},
    # I. 국제/교환
    {"category_id": "I", "category_name": "국제", "subcategory": "교환학생 신청 방법"},
    {"category_id": "I", "category_name": "국제", "subcategory": "해외 파견 장학금"},
    {"category_id": "I", "category_name": "국제", "subcategory": "외국인 유학생 지원"},
    {"category_id": "I", "category_name": "국제", "subcategory": "어학 프로그램"},
    # J. 비교과/대외활동
    {"category_id": "J", "category_name": "비교과", "subcategory": "비교과 프로그램 신청"},
    {"category_id": "J", "category_name": "비교과", "subcategory": "봉사활동 인정"},
    {"category_id": "J", "category_name": "비교과", "subcategory": "학술대회 참가 지원"},
    {"category_id": "J", "category_name": "비교과", "subcategory": "자격증 취득 지원"},
    # K. 공지사항
    {"category_id": "K", "category_name": "공지", "subcategory": "학사 공지 확인 방법"},
    {"category_id": "K", "category_name": "공지", "subcategory": "일반 공지 및 행사"},
    {"category_id": "K", "category_name": "공지", "subcategory": "학과별 공지 확인"},
    {"category_id": "K", "category_name": "공지", "subcategory": "긴급 공지 및 휴강"},
    # L. 학교 일반
    {"category_id": "L", "category_name": "학교일반", "subcategory": "충남대 역사 및 소개"},
    {"category_id": "L", "category_name": "학교일반", "subcategory": "캠퍼스 지도 및 접근"},
    {"category_id": "L", "category_name": "학교일반", "subcategory": "학교 주요 연락처"},
    {"category_id": "L", "category_name": "학교일반", "subcategory": "입학 및 전형 정보"},
    # Z. 도메인 밖 (거절 대상)
    {"category_id": "Z", "category_name": "도메인밖", "subcategory": "날씨 및 기상 정보"},
    {"category_id": "Z", "category_name": "도메인밖", "subcategory": "정치/사회 이슈"},
    {"category_id": "Z", "category_name": "도메인밖", "subcategory": "연예/스포츠"},
    {"category_id": "Z", "category_name": "도메인밖", "subcategory": "타 대학 정보"},
    {"category_id": "Z", "category_name": "도메인밖", "subcategory": "일반 상식 퀴즈"},
]

SYSTEM_PROMPT = """당신은 충남대학교 학생/교직원이 실제로 물어볼 법한 질문을 생성하는 전문가입니다.
자연스러운 한국어로, 다양한 문체(격식체/비격식체/구어체)를 섞어 질문을 생성하세요.
각 질문은 JSON 배열 형식으로 반환하고, 다른 텍스트는 절대 포함하지 마세요."""


def _build_prompt(node: Dict, count: int) -> str:
    return f"""충남대학교 '{node["category_name"]}' 카테고리 중 '{node["subcategory"]}' 주제로
실제 학생/교직원이 물어볼 법한 질문 {count}개를 생성하세요.

요구사항:
- 충남대학교 맥락에 맞는 구체적 질문
- 다양한 문체 (격식체, 비격식체, 구어체 혼합)
- 질문 의도가 명확할 것
- 중복 없이 다양하게

JSON 배열로만 응답 (다른 텍스트 없음):
[
  {{"question": "질문 내용", "intent": "질문 의도 한 줄 요약"}},
  ...
]"""


def generate_question_pool(output_path: str = None, limit: int = None) -> List[Dict]:
    """Claude Sonnet API로 카테고리별 질문 풀 생성"""
    if output_path is None:
        output_path = str(Path(__file__).parent.parent / "data" / "questions" / "question_pool.jsonl")

    limit = limit or int(os.environ.get("QUESTION_LIMIT", "1000"))
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # 노드당 생성할 질문 수 계산
    n_nodes = len(CATEGORY_NODES)
    per_node = max(10, min(150, limit // n_nodes))

    client = anthropic.Anthropic(api_key=api_key) if api_key else None
    all_questions: List[Dict] = []
    total_generated = 0

    with open(output_path, "w", encoding="utf-8") as f:
        for node in CATEGORY_NODES:
            if total_generated >= limit:
                break

            remaining = limit - total_generated
            count = min(per_node, remaining)

            questions = _generate_for_node(client, node, count)

            for q in questions:
                item = {
                    "category_id": node["category_id"],
                    "category_name": node["category_name"],
                    "subcategory": node["subcategory"],
                    "question": q.get("question", ""),
                    "intent": q.get("intent", ""),
                }
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
                all_questions.append(item)
                total_generated += 1

            print(f"[{node['category_id']}] {node['subcategory']}: {len(questions)}개 생성 (누적 {total_generated})")

            # API 속도 제한 방지
            if client:
                time.sleep(0.5)

    print(f"\n총 {total_generated}개 질문 생성 완료 → {output_path}")
    return all_questions


def _generate_for_node(client, node: Dict, count: int) -> List[Dict]:
    """단일 노드에 대해 질문 생성 (API 없으면 더미 반환)"""
    if client is None:
        return _fallback_questions(node, count)

    prompt = _build_prompt(node, count)
    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
            system=SYSTEM_PROMPT,
        )
        raw = response.content[0].text.strip()
        # JSON 파싱
        if raw.startswith("["):
            return json.loads(raw)
        # 코드블록 제거
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except Exception as e:
        print(f"  API 오류 ({node['subcategory']}): {e} → 더미 사용")
        return _fallback_questions(node, count)


def _fallback_questions(node: Dict, count: int) -> List[Dict]:
    """API 없을 때 더미 질문 반환"""
    templates = [
        f"충남대 {node['subcategory']}에 대해 알려주세요.",
        f"{node['subcategory']} 방법이 어떻게 되나요?",
        f"충남대에서 {node['subcategory']} 어디서 할 수 있나요?",
        f"{node['subcategory']} 관련해서 문의드립니다.",
        f"충남대 {node['subcategory']} 담당 부서가 어디인가요?",
    ]
    result = []
    for i in range(count):
        result.append({
            "question": templates[i % len(templates)],
            "intent": f"{node['subcategory']} 조회",
        })
    return result


if __name__ == "__main__":
    generate_question_pool()
