"""Gradio 시연 UI (AC16). launch_app() 실행 시 share URL 발급."""


def launch_app(share: bool = True):
    import gradio as gr
    from interface.answer_questions import _rag_answer

    def chat(message: str, history: list) -> str:
        try:
            answer, top_docs, rejected = _rag_answer(message, return_context=True)
            # 출처 메타데이터 표시 (거절이 아닌 경우)
            if not rejected and top_docs:
                sources = []
                for d in top_docs:
                    meta = d.get("metadata", d)
                    url = meta.get("source_url", "")
                    updated = meta.get("last_crawled_at", "")
                    if url and url not in [s[0] for s in sources]:
                        sources.append((url, updated))
                if sources and "출처" not in answer:
                    src_lines = "\n".join(
                        f"- {url} (업데이트: {upd})" for url, upd in sources[:3]
                    )
                    answer = answer.rstrip() + f"\n\n**참고 출처**\n{src_lines}"
            return answer
        except Exception as e:
            return f"오류가 발생했습니다: {e}"

    demo = gr.ChatInterface(
        fn=chat,
        title="충남대학교 학내정보 챗봇",
        description="충남대 학식, 도서관, 장학금, 수강신청 등 학내 정보를 질문하세요.",
        examples=[
            "오늘 학식 메뉴가 뭐예요?",
            "도서관 열람실 몇 시까지 해요?",
            "국가장학금 신청 방법 알려주세요",
            "수강신청 정정 기간이 언제예요?",
        ],
        theme=gr.themes.Soft(),
    )
    demo.launch(share=share, server_name="0.0.0.0")
    return demo


if __name__ == "__main__":
    launch_app()
