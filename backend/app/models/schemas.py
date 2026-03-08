"""
============================================================
 Pydantic 스키마 (DTO)
============================================================
 API 요청/응답의 데이터 구조를 정의
 노션 API의 복잡한 JSON을 클라이언트가 쓰기 쉬운 형태로 변환
============================================================
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


# ============================================================
#  퀘스트 관련
# ============================================================

class QuestCategory(str, Enum):
    """퀘스트 카테고리 (위젯의 카테고리 아이콘과 매핑)"""
    DEV = "dev"
    STUDY = "study"
    LIFE = "life"
    WORK = "work"
    ETC = "etc"


class QuestDifficulty(str, Enum):
    """난이도별 XP 차등 부여"""
    EASY = "easy"           # 15 XP
    MEDIUM = "medium"       # 30 XP
    HARD = "hard"           # 50 XP
    LEGENDARY = "legendary" # 100 XP


class QuestDTO(BaseModel):
    """
    노션 → 위젯으로 전달되는 퀘스트 DTO
    노션 API 응답의 수십 개 필드 중 위젯에 필요한 것만 추출
    """
    id: str = Field(description="노션 페이지 ID")
    name: str = Field(description="퀘스트 제목")
    category: QuestCategory = Field(default=QuestCategory.ETC, description="카테고리")
    difficulty: QuestDifficulty = Field(default=QuestDifficulty.MEDIUM, description="난이도")
    xp: int = Field(default=30, description="보상 경험치")
    completed: bool = Field(default=False, description="완료 여부")
    due_date: Optional[str] = Field(default=None, description="마감일")


class QuestListResponse(BaseModel):
    """오늘의 퀘스트 목록 응답"""
    quests: list[QuestDTO]
    total: int
    synced_at: str = Field(description="동기화 시각")


# ============================================================
#  AI 검증 관련
# ============================================================

class VerifyRequest(BaseModel):
    """
    퀘스트 증명 제출 요청
    위젯에서 증명 모달을 통해 제출한 데이터가 이 형태로 전달됨
    """
    task_id: str = Field(description="검증할 퀘스트의 노션 페이지 ID")
    quest_title: str = Field(description="퀘스트 제목 (프롬프트에 포함)")
    category: QuestCategory = Field(default=QuestCategory.ETC, description="퀘스트 카테고리")
    difficulty: QuestDifficulty = Field(default=QuestDifficulty.MEDIUM, description="퀘스트 난이도")
    proof_text: Optional[str] = Field(default=None, description="텍스트 증명 (코드, 요약 등)")
    proof_image_base64: Optional[str] = Field(default=None, description="이미지 증명 (base64)")


class VerifyResult(BaseModel):
    """
    Gemini AI가 반환하는 구조화된 검증 결과
    is_passed + confidence_score + npc_feedback 형태를 강제
    """
    is_passed: bool = Field(description="검증 통과 여부")
    confidence_score: float = Field(ge=0.0, le=1.0, description="AI 확신도 (0.0~1.0)")
    npc_feedback: str = Field(description="NPC 캐릭터 톤의 피드백 메시지")


class VerifyResponse(BaseModel):
    """검증 API 최종 응답 (AI 결과 + 보상 정보)"""
    task_id: str
    result: VerifyResult
    xp_earned: int = Field(default=0, description="획득한 XP (통과 시에만)")
    level_up: bool = Field(default=False, description="레벨업 발생 여부")
    new_level: Optional[int] = Field(default=None, description="레벨업 시 새 레벨")


# ============================================================
#  유저 상태 관련
# ============================================================

class UserStats(BaseModel):
    """유저의 현재 게임 상태 (위젯 HUD에 렌더링)"""
    name: str = Field(default="Player")
    level: int = Field(default=1)
    current_xp: int = Field(default=0, description="현재 레벨 내 경험치")
    xp_to_next: int = Field(default=100, description="다음 레벨까지 필요 경험치")
    total_xp: int = Field(default=0, description="누적 총 경험치")
    title: str = Field(default="초보 모험가", description="장착 중인 칭호")
    completed_count: int = Field(default=0, description="총 완료 퀘스트 수")
    streak: int = Field(default=0, description="연속 완료 콤보")


class UserStatsUpdate(BaseModel):
    """유저 상태 수동 업데이트 (닉네임 변경 등)"""
    name: Optional[str] = None


# ============================================================
#  히스토리 관련
# ============================================================

class QuestLog(BaseModel):
    """완료된 퀘스트 기록 한 건"""
    quest_title: str
    category: QuestCategory
    difficulty: QuestDifficulty
    xp_earned: int
    ai_feedback: str = Field(description="AI가 남긴 NPC 피드백")
    completed_at: str = Field(description="완료 시각")
    had_proof: bool = Field(default=False, description="증명 자료 첨부 여부")


class HistoryResponse(BaseModel):
    """퀘스트 로그 목록 응답"""
    logs: list[QuestLog]
    total: int
