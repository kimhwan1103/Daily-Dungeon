"""
============================================================
 유저 상태 및 히스토리 라우터
============================================================
 GET  /api/user/stats     현재 유저 상태 (레벨, XP, 칭호)
 PATCH /api/user/stats    유저 정보 수정 (닉네임 등)
 GET  /api/history        퀘스트 완료 기록 조회
============================================================
"""

from fastapi import APIRouter

from ..models.schemas import UserStats, UserStatsUpdate, HistoryResponse
from ..services import game_service

router = APIRouter(prefix="/api", tags=["user"])


@router.get("/user/stats", response_model=UserStats)
def get_user_stats():
    """
    현재 유저 상태 조회

    위젯이 시작될 때, 또는 주기적으로 호출하여
    레벨, 경험치 바, 칭호 등 HUD를 렌더링하는 데 사용
    """
    return game_service.get_user_stats()


@router.patch("/user/stats", response_model=UserStats)
def update_user_stats(update: UserStatsUpdate):
    """유저 정보 수정 (현재는 닉네임만)"""
    if update.name:
        return game_service.update_user_name(update.name)
    return game_service.get_user_stats()


@router.get("/history", response_model=HistoryResponse)
def get_history():
    """
    퀘스트 완료 기록 조회 (최신순)

    위젯의 '📜 기록' 탭에서 열람
    각 기록에는 퀘스트 제목, 획득 XP, AI 피드백, 완료 시각 등 포함
    """
    logs = game_service.get_quest_logs()
    return HistoryResponse(
        logs=logs,
        total=len(logs),
    )
