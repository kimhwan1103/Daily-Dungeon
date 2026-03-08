"""
============================================================
 퀘스트 라우터 - 노션 동기화 엔드포인트
============================================================
 GET  /api/quests/today     오늘의 퀘스트 조회 (노션에서 가져옴)
 PATCH /api/quests/{id}/complete  퀘스트 완료 처리 (노션에 반영)
============================================================
"""

from fastapi import APIRouter, HTTPException
from datetime import datetime

from ..models.schemas import QuestListResponse, QuestDTO
from ..services import notion_service

router = APIRouter(prefix="/api/quests", tags=["quests"])


@router.get("/today", response_model=QuestListResponse)
async def get_today_quests():
    """
    오늘의 퀘스트 목록 조회

    노션 데이터베이스에서 오늘 날짜이거나 미완료인 태스크를 가져와
    위젯에서 사용하기 편한 DTO 형태로 반환

    위젯에서 '새로고침' 버튼을 누르거나 앱 시작 시 호출
    """
    try:
        quests = await notion_service.fetch_today_quests()
        return QuestListResponse(
            quests=quests,
            total=len(quests),
            synced_at=datetime.now().isoformat(),
        )
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"노션 API 연동 실패: {str(e)[:200]}",
        )


@router.patch("/{task_id}/complete")
async def complete_quest(task_id: str):
    """
    퀘스트 완료 처리 → 노션 동기화

    AI 검증을 통과한 후 내부적으로 호출됨
    노션 페이지의 Done 체크박스를 true로 변경하여
    노션과 위젯의 상태를 일치시킴
    """
    success = await notion_service.mark_quest_complete(task_id)
    if not success:
        raise HTTPException(
            status_code=502,
            detail="노션 페이지 업데이트에 실패했습니다.",
        )
    return {"status": "ok", "task_id": task_id}
