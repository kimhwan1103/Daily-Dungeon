"""
============================================================
 퀘스트 라우터 - 노션 동기화 / DB 직접 관리
============================================================
 모드에 따라 퀘스트 소스가 달라짐:
 - SQLite (기본): 노션 API에서 퀘스트를 동기화
 - 외부 DB (PostgreSQL/MySQL): DB에서 직접 CRUD

 퀘스트 타입:
 - main: 메인 퀘스트 (장기 핵심 목표, XP 2.5배)
 - sub: 서브 퀘스트 (일반 단발성)
 - daily: 일일 반복 퀘스트 (스트릭 연동)

 GET   /api/quests/today                오늘의 퀘스트 조회
 POST  /api/quests/add                  퀘스트 추가 (DB 모드)
 PATCH /api/quests/{id}/complete        퀘스트 완료 처리
 DELETE /api/quests/{id}                퀘스트 삭제 (DB 모드)
 POST  /api/quests/sub-quest/toggle     세부 퀘스트 체크 토글
 POST  /api/quests/{id}/daily-complete  일일 퀘스트 완료 처리
============================================================
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

from ..config import settings
from ..models.schemas import (
    QuestListResponse, QuestDTO,
    SubQuestToggleResponse, DailyCompleteResponse,
)
from ..services import notion_service, game_service
from ..services import quest_db_service

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
    오늘의 퀘스트 목록 조회

    - 노션 모드: 노션 데이터베이스에서 동기화
    - DB 모드: DB에서 직접 조회
    """
    try:
        if settings.is_db_mode:
            quests = quest_db_service.fetch_all_quests()
        else:
            quests = await notion_service.fetch_today_quests()

        return QuestListResponse(
            quests=quests,
            total=len(quests),
            synced_at=datetime.now().isoformat(),
        )
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"퀘스트 조회 실패: {str(e)[:200]}",
        )


# ============================================================
#  퀘스트 추가 (DB 모드 전용)
# ============================================================

class AddQuestRequest(BaseModel):
    name: str
    category: str = "etc"
    difficulty: str = "medium"
    quest_type: str = "sub"  # main/sub/daily
    is_daily: bool = False


@router.post("/add", response_model=QuestDTO)
async def add_quest(req: AddQuestRequest):
    """퀘스트 추가 (DB 모드에서만 사용)"""
    if not settings.is_db_mode:
        raise HTTPException(
            status_code=400,
            detail="노션 모드에서는 노션에서 직접 퀘스트를 추가하세요.",
        )
    try:
        quest = quest_db_service.add_quest(
            name=req.name,
            category=req.category,
            difficulty=req.difficulty,
            quest_type=req.quest_type,
            is_daily=req.is_daily,
        )
        return quest
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"퀘스트 추가 실패: {str(e)[:200]}")


@router.patch("/{task_id}/complete")
async def complete_quest(task_id: str):
    """퀘스트 완료 처리"""
    if settings.is_db_mode:
        success = quest_db_service.mark_complete(task_id)
    else:
        success = await notion_service.mark_quest_complete(task_id)

    if not success:
        raise HTTPException(
            status_code=502,
            detail="퀘스트 완료 처리에 실패했습니다.",
        )
    return {"status": "ok", "task_id": task_id}


@router.delete("/{task_id}")
async def delete_quest(task_id: str):
    """퀘스트 삭제 (DB 모드에서만 사용)"""
    if not settings.is_db_mode:
        raise HTTPException(
            status_code=400,
            detail="노션 모드에서는 노션에서 직접 퀘스트를 삭제하세요.",
        )
    success = quest_db_service.delete_quest(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="퀘스트를 찾을 수 없습니다.")
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
    # 모드에 따라 업데이트
    if settings.is_db_mode:
        success = quest_db_service.toggle_sub_quest(req.block_id, req.checked)
    else:
        success = await notion_service.toggle_sub_quest(req.block_id, req.checked)

    if not success:
        raise HTTPException(status_code=502, detail="세부 퀘스트 업데이트 실패")

    xp_earned = 0
    bonus_xp = 0
    all_done = False
    level_up = False
    new_level = None

    if req.checked:
        xp_earned = SUB_QUEST_XP

        # 전체 세부 퀘스트 완료 여부 확인
        if settings.is_db_mode:
            sub_quests = quest_db_service.fetch_sub_quests(req.page_id)
        else:
            sub_quests = await notion_service.fetch_page_sub_quests(req.page_id)

        if sub_quests and all(sq.checked for sq in sub_quests):
            all_done = True
            bonus_xp = SUB_QUEST_ALL_DONE_BONUS

        total_xp = xp_earned + bonus_xp
        _, level_up, new_level = game_service.grant_xp_only(total_xp)

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
    - DB 모드: DB에서 완료 처리
    - 노션 모드: 노션에 Done 체크박스 반영
    """
    # 모드에 따라 완료 처리
    if settings.is_db_mode:
        quest_db_service.mark_complete(task_id)
    else:
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
