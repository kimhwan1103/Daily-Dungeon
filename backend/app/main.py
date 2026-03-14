"""
============================================================
 Quest Widget - FastAPI 백엔드 진입점
============================================================
 구조:
   /api/quests/today                → 노션에서 오늘의 퀘스트 동기화
   /api/quests/{id}/complete        → 노션에 완료 상태 반영
   /api/quests/sub-quest/toggle     → 세부 퀘스트 체크 토글
   /api/quests/{id}/daily-complete  → 일일 퀘스트 완료 처리
   /api/verify                      → AI(Gemini) 작업 증명 검증
   /api/user/stats                  → 유저 레벨/XP 조회 및 수정
   /api/history                     → 완료 퀘스트 히스토리

 실행:
   cd backend
   uvicorn app.main:app --reload
============================================================
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routers import quests, verify, user
from .services.scheduler_service import start_scheduler, stop_scheduler
from .models.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작/종료 시 DB 초기화 + 스케줄러 관리"""
    init_db()  # 테이블 자동 생성 (없으면 CREATE, 있으면 유지)
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title="Quest Widget API",
    description="게이미피케이션 할일 위젯 백엔드 - 노션 동기화, AI 검증, 게임 상태 관리",
    version="1.0.0",
    lifespan=lifespan,
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
app.include_router(quests.router)   # 노션 동기화 + 세부/일일 퀘스트
app.include_router(verify.router)   # AI 검증
app.include_router(user.router)     # 유저 상태 + 히스토리


@app.get("/")
def health_check():
    """서버 상태 확인용"""
    return {"status": "ok", "service": "Quest Widget API"}


@app.get("/api/mode")
def get_mode():
    """현재 동작 모드 반환 (프론트엔드 UI 분기용)"""
    return {
        "db_mode": settings.is_db_mode,
        "mode": "db" if settings.is_db_mode else "notion",
    }
