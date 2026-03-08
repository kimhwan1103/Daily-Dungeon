"""
============================================================
 Quest Widget - FastAPI 백엔드 진입점
============================================================
 구조:
   /api/quests/today          → 노션에서 오늘의 퀘스트 동기화
   /api/quests/{id}/complete  → 노션에 완료 상태 반영
   /api/verify                → AI(Gemini) 작업 증명 검증
   /api/user/stats            → 유저 레벨/XP 조회 및 수정
   /api/history               → 완료 퀘스트 히스토리

 실행:
   cd backend
   uvicorn app.main:app --reload
============================================================
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import quests, verify, user

app = FastAPI(
    title="Quest Widget API",
    description="게이미피케이션 할일 위젯 백엔드 - 노션 동기화, AI 검증, 게임 상태 관리",
    version="1.0.0",
)

# ============================================================
#  CORS 설정
# ============================================================
#  Electron 위젯에서 localhost FastAPI로 요청을 보내므로
#  CORS를 허용해야 함 (file:// 프로토콜 + localhost 혼합)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 로컬 위젯 전용이므로 전체 허용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
#  라우터 등록
# ============================================================
app.include_router(quests.router)   # 노션 동기화
app.include_router(verify.router)   # AI 검증
app.include_router(user.router)     # 유저 상태 + 히스토리


@app.get("/")
def health_check():
    """서버 상태 확인용"""
    return {"status": "ok", "service": "Quest Widget API"}
