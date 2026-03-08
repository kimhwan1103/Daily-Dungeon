"""
============================================================
 3. 게임 상태 및 로컬 JSON DB 모듈
============================================================
 TinyDB를 사용하여 로컬 database.json에 유저 상태를 저장/조회

 저장 데이터:
 - user_stats: 레벨, 경험치, 칭호, 연속 콤보 등
 - quest_logs: 완료된 퀘스트 히스토리

 레벨업 커브:
 - 다음 레벨 요구 XP = floor(현재 요구 XP * 1.4)
 - Lv1→2: 100 XP / Lv2→3: 140 XP / Lv3→4: 196 XP ...
============================================================
"""

from datetime import datetime
from tinydb import TinyDB, Query
from typing import Optional
import math

from ..config import settings
from ..models.schemas import (
    UserStats,
    QuestLog,
    QuestCategory,
    QuestDifficulty,
)

# ============================================================
#  TinyDB 초기화
# ============================================================
#  database.json 파일 하나에 두 개의 테이블(table)을 사용:
#  - "user": 유저 상태 (항상 1개의 문서만 존재)
#  - "quest_logs": 완료 기록 (문서가 계속 추가됨)

db = TinyDB(settings.DB_PATH, ensure_ascii=False, encoding="utf-8")
user_table = db.table("user")
logs_table = db.table("quest_logs")

# 레벨별 칭호 매핑
TITLES = [
    (1, "초보 모험가"),
    (3, "수련생"),
    (5, "전사"),
    (8, "정예 기사"),
    (12, "챔피언"),
    (20, "전설"),
]


def _get_title(level: int) -> str:
    """레벨에 맞는 칭호 반환"""
    title = TITLES[0][1]
    for lv, t in TITLES:
        if level >= lv:
            title = t
    return title


# ============================================================
#  유저 상태 관리
# ============================================================

def get_user_stats() -> UserStats:
    """
    현재 유저 상태를 DB에서 조회

    DB에 데이터가 없으면 초기 상태를 생성하여 반환
    위젯은 이 데이터로 레벨, XP 바, 칭호 등을 렌더링
    """
    all_users = user_table.all()

    if not all_users:
        # 최초 실행 시 초기 상태 생성
        initial = {
            "name": "Player",
            "level": 1,
            "current_xp": 0,
            "xp_to_next": 100,
            "total_xp": 0,
            "title": "초보 모험가",
            "completed_count": 0,
            "streak": 0,
        }
        user_table.insert(initial)
        return UserStats(**initial)

    data = all_users[0]
    return UserStats(**data)


def update_user_name(name: str) -> UserStats:
    """닉네임 변경"""
    User = Query()
    all_users = user_table.all()

    if all_users:
        user_table.update({"name": name}, doc_ids=[all_users[0].doc_id])
    else:
        user_table.insert({"name": name, "level": 1, "current_xp": 0,
                           "xp_to_next": 100, "total_xp": 0,
                           "title": "초보 모험가", "completed_count": 0, "streak": 0})

    return get_user_stats()


def grant_xp(xp_amount: int) -> tuple[UserStats, bool, Optional[int]]:
    """
    경험치 부여 및 레벨업 처리

    Args:
        xp_amount: 획득할 경험치

    Returns:
        (업데이트된 유저 상태, 레벨업 여부, 새 레벨 or None)

    레벨업 로직:
        1. 현재 XP에 획득 XP를 더함
        2. 현재 XP >= 요구 XP이면 레벨업
           - 레벨 +1
           - 남은 XP = 현재 XP - 요구 XP (이월)
           - 새 요구 XP = floor(이전 요구 XP * 1.4)
        3. 다중 레벨업 가능 (while 루프)
    """
    stats = get_user_stats()

    new_xp = stats.current_xp + xp_amount
    new_total = stats.total_xp + xp_amount
    new_level = stats.level
    xp_to_next = stats.xp_to_next
    leveled_up = False
    new_completed = stats.completed_count + 1
    new_streak = stats.streak + 1

    # 레벨업 체크 (다중 레벨업 대응)
    while new_xp >= xp_to_next:
        new_xp -= xp_to_next
        new_level += 1
        xp_to_next = math.floor(xp_to_next * 1.4)  # 레벨업 커브: 1.4배
        leveled_up = True

    new_title = _get_title(new_level)

    # DB 업데이트
    updated = {
        "name": stats.name,
        "level": new_level,
        "current_xp": new_xp,
        "xp_to_next": xp_to_next,
        "total_xp": new_total,
        "title": new_title,
        "completed_count": new_completed,
        "streak": new_streak,
    }

    all_users = user_table.all()
    if all_users:
        user_table.update(updated, doc_ids=[all_users[0].doc_id])
    else:
        user_table.insert(updated)

    return (
        UserStats(**updated),
        leveled_up,
        new_level if leveled_up else None,
    )


def reset_streak():
    """콤보 리셋 (검증 실패 시)"""
    all_users = user_table.all()
    if all_users:
        user_table.update({"streak": 0}, doc_ids=[all_users[0].doc_id])


# ============================================================
#  퀘스트 히스토리 (완료 기록)
# ============================================================

def add_quest_log(
    quest_title: str,
    category: str,
    difficulty: str,
    xp_earned: int,
    ai_feedback: str,
    had_proof: bool = False,
):
    """
    퀘스트 완료 기록을 quest_logs 테이블에 추가

    AI 검증 통과 후 호출되어, 퀘스트 제목/카테고리/XP/피드백을 기록
    위젯의 '📜 기록' 탭에서 열람 가능
    """
    logs_table.insert({
        "quest_title": quest_title,
        "category": category,
        "difficulty": difficulty,
        "xp_earned": xp_earned,
        "ai_feedback": ai_feedback,
        "completed_at": datetime.now().isoformat(),
        "had_proof": had_proof,
    })


def get_quest_logs(limit: int = 50) -> list[QuestLog]:
    """
    퀘스트 완료 기록을 최신순으로 조회

    Args:
        limit: 최대 반환 개수 (기본 50건)

    Returns:
        최신순 정렬된 QuestLog 리스트
    """
    all_logs = logs_table.all()

    # 최신순 정렬 (completed_at 기준 역순)
    all_logs.sort(key=lambda x: x.get("completed_at", ""), reverse=True)

    result = []
    for log in all_logs[:limit]:
        try:
            result.append(QuestLog(
                quest_title=log["quest_title"],
                category=QuestCategory(log.get("category", "etc")),
                difficulty=QuestDifficulty(log.get("difficulty", "medium")),
                xp_earned=log["xp_earned"],
                ai_feedback=log.get("ai_feedback", ""),
                completed_at=log["completed_at"],
                had_proof=log.get("had_proof", False),
            ))
        except (KeyError, ValueError):
            continue

    return result


def reset_all():
    """전체 데이터 초기화 (디버그/설정용)"""
    db.drop_tables()
