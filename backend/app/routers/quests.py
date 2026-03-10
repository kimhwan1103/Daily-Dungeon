"""
============================================================
 퀘스트 라우터 - 노션 동기화 엔드포인트
============================================================
 GET   /api/quests/today                오늘의 퀘스트 조회
 PATCH /api/quests/{id}/complete        퀘스트 완료 처리
 POST  /api/quests/sub-quest/toggle     세부 퀘스트 체크 토글
 POST  /api/quests/{id}/daily-complete  일일 퀘스트 완료 처리
============================================================
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime

from ..models.schemas import (
    QuestListResponse, QuestDTO,
    SubQuestToggleResponse, DailyCompleteResponse,
)
from ..services import notion_service, game_service

router = APIRouter(prefix="/api/quests", tags=["quests"])

# 난이도별 XP (일일 퀘스트용)
DIFFICULTY_XP = {
    "easy": 15,
    "medium": 30,
    "hard": 50,
    "legendary": 100,
}

# 세부 퀘스트 XP
SUB_QUEST_XP = 10
SUB_QUEST_ALL_DONE_BONUS = 100


@router.get("/today", response_model=QuestListResponse)
async def get_today_quests():
    """
    오늘의 퀘스트 목록 조회 (세부 퀘스트 포함)

    노션 데이터베이스에서 오늘 날짜이거나 미완료인 태스크를 가져와
    각 퀘스트의 페이지 내부 to_do 블록도 세부 퀘스트로 함께 반환
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
    """퀘스트 완료 처리 → 노션 동기화"""
    success = await notion_service.mark_quest_complete(task_id)
    if not success:
        raise HTTPException(
            status_code=502,
            detail="노션 페이지 업데이트에 실패했습니다.",
        )
    return {"status": "ok", "task_id": task_id}


# ============================================================
#  세부 퀘스트 (Sub-quest) 엔드포인트
# ============================================================

class SubQuestToggleRequest(BaseModel):
    block_id: str
    checked: bool
    page_id: str  # 부모 퀘스트 ID (전체 완료 체크용)


@router.post("/sub-quest/toggle", response_model=SubQuestToggleResponse)
async def toggle_sub_quest(req: SubQuestToggleRequest):
    """
    세부 퀘스트(to_do 블록) 체크 토글

    - 체크 시: +10 XP
    - 체크 해제 시: XP 변동 없음
    - 모든 세부 퀘스트 완료 시: +100 XP 보너스
    """
    # 노션 블록 업데이트
    success = await notion_service.toggle_sub_quest(req.block_id, req.checked)
    if not success:
        raise HTTPException(status_code=502, detail="세부 퀘스트 업데이트 실패")

    xp_earned = 0
    bonus_xp = 0
    all_done = False
    level_up = False
    new_level = None

    if req.checked:
        # 체크 시 XP 부여
        xp_earned = SUB_QUEST_XP

        # 전체 세부 퀘스트 완료 여부 확인
        sub_quests = await notion_service.fetch_page_sub_quests(req.page_id)
        if sub_quests and all(sq.checked for sq in sub_quests):
            all_done = True
            bonus_xp = SUB_QUEST_ALL_DONE_BONUS

        total_xp = xp_earned + bonus_xp
        _, level_up, new_level = game_service.grant_xp_only(total_xp)

        # 히스토리에 기록
        game_service.add_quest_log(
            quest_title=f"[세부] 체크리스트 완료",
            category="etc",
            difficulty="easy",
            xp_earned=total_xp,
            ai_feedback="세부 퀘스트 완료!" + (" 🎉 전체 완료 보너스!" if all_done else ""),
            had_proof=False,
        )

    return SubQuestToggleResponse(
        block_id=req.block_id,
        checked=req.checked,
        xp_earned=xp_earned,
        all_done=all_done,
        bonus_xp=bonus_xp,
        level_up=level_up,
        new_level=new_level,
    )


# ============================================================
#  일일 퀘스트 (Daily Quest) 엔드포인트
# ============================================================

class DailyCompleteRequest(BaseModel):
    task_id: str
    quest_title: str
    difficulty: str = "medium"


@router.post("/{task_id}/daily-complete", response_model=DailyCompleteResponse)
async def complete_daily_quest(task_id: str, req: DailyCompleteRequest):
    """
    일일 퀘스트 완료 처리

    AI 검증 없이 체크만으로 완료
    - 난이도에 따른 XP 부여
    - 7일 연속 완료 시 주간 보너스 (200 XP)
    - 노션에 Done 체크박스 반영
    """
    # 노션에 완료 반영
    await notion_service.mark_quest_complete(task_id)

    # XP 부여 + 일일 스트릭 처리
    xp = DIFFICULTY_XP.get(req.difficulty, 30)
    stats, level_up, new_level, daily_streak, weekly_bonus, weekly_bonus_xp = \
        game_service.complete_daily_quest(xp)

    # 히스토리 기록
    feedback = f"일일 퀘스트 완료! (연속 {daily_streak}일)"
    if weekly_bonus:
        feedback += f" 🎊 7일 연속 보너스! +{weekly_bonus_xp} XP"

    game_service.add_quest_log(
        quest_title=req.quest_title,
        category="etc",
        difficulty=req.difficulty,
        xp_earned=xp + weekly_bonus_xp,
        ai_feedback=feedback,
        had_proof=False,
    )

    return DailyCompleteResponse(
        task_id=task_id,
        xp_earned=xp,
        daily_streak=daily_streak,
        weekly_bonus=weekly_bonus,
        weekly_bonus_xp=weekly_bonus_xp,
        level_up=level_up,
        new_level=new_level,
    )
