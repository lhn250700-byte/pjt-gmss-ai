# aichatpy (기능 이전됨)

**AI 상담 API는 `testchatpy` 한 서버로 통합되었습니다.**

- 동일 기능: `GET/POST /api/ai/chat/{cnsl_id}`, `POST /api/ai/chat/{cnsl_id}/summary`
- 배포: Render에서 **testchatpy** 하나만 사용하고, 프론트의 `VITE_AI_CHAT_API_URL`(및 요약용 URL)을 testchatpy 서비스 URL로 설정하면 됩니다.
- 코드 위치: 프로젝트 루트의 **testchatpy** (FastAPI + ai_chat 라우터, ai_db, ai_openai).

이 폴더(aichatpy)는 참고용으로만 두었으며, 신규 배포/개발은 testchatpy를 사용하세요.
