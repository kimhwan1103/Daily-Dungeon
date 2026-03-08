"""
============================================================
 AI 검증 라우터 - 작업 증명 제출 및 검증
============================================================
 POST /api/verify   퀘스트 증명 제출 → AI 검증 → 결과 반환

 이 엔드포인트가 시스템의 핵심 파이프라인:
 1. 증명 데이터 수신
 2. Gemini AI로 검증
 3. 통과 시: 경험치 부여 + 노션 완료 처리 + 히스토리 기록
 4. 실패 시: 피드백 반환 + 콤보 리셋
============================================================
"""

from fastapi import APIRouter, HTTPException

from ..models.schemas import VerifyRequest, VerifyResponse
from ..services import gemini_service, game_service, notion_service

router = APIRouter(prefix="/api", tags=["verify"])

# 난이도별 XP
DIFFICULTY_XP = {
    "easy": 15,
    "medium": 30,
    "hard": 50,
    "legendary": 100,
}


@router.post("/verify", response_model=VerifyResponse)
async def verify_quest(req: VerifyRequest):
    """
    퀘스트 작업 증명 제출 및 AI 검증

    전체 흐름:
    ┌─────────────────────────────────────────┐
    │ 위젯에서 증명 제출                        │
    │   ↓                                     │
    │ Gemini AI 검증 (NPC 길드마스터 역할)       │
    │   ↓                                     │
    │ 통과? ─── Yes ──→ 경험치 부여             │
    │   │              노션 완료 처리           │
    │   │              히스토리 기록             │
    │   │              NPC 칭찬 피드백           │
    │   │                                     │
    │   └── No ───→ 콤보 리셋                  │
    │              NPC 격려 + 부족 사유 피드백    │
    └─────────────────────────────────────────┘
    """
    # 1단계: Gemini AI에 검증 요청
    try:
        result = await gemini_service.verify_quest_proof(
            quest_title=req.quest_title,
            proof_text=req.proof_text,
            proof_image_base64=req.proof_image_base64,
        )
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"AI 검증 서비스 오류: {str(e)[:200]}",
        )

    xp_earned = 0
    level_up = False
    new_level = None

    if result.is_passed:
        # 2단계 (통과): 경험치 부여 + 레벨업 체크
        xp_earned = DIFFICULTY_XP.get(req.difficulty.value, 30)
        stats, level_up, new_level = game_service.grant_xp(xp_earned)

        # 3단계: 노션에 완료 상태 반영
        try:
            await notion_service.mark_quest_complete(req.task_id)
        except Exception:
            pass  # 노션 동기화 실패해도 XP는 이미 부여됨

        # 4단계: 히스토리에 기록
        game_service.add_quest_log(
            quest_title=req.quest_title,
            category=req.category.value,
            difficulty=req.difficulty.value,
            xp_earned=xp_earned,
            ai_feedback=result.npc_feedback,
            had_proof=bool(req.proof_text or req.proof_image_base64),
        )

    else:
        # 실패 시: 연속 콤보 리셋
        game_service.reset_streak()

    return VerifyResponse(
        task_id=req.task_id,
        result=result,
        xp_earned=xp_earned,
        level_up=level_up,
        new_level=new_level,
    )
