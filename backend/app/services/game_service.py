"""
============================================================
 3. 게임 상태 및 DB 모듈
============================================================
 SQLAlchemy를 통해 다양한 DB 백엔드를 지원
 - SQLite (기본, 로컬 파일)
 - PostgreSQL / MySQL (DATABASE_URL 설정)

 저장 데이터:
 - user_stats: 레벨, 경험치, 칭호, 연속 콤보 등
 - quest_logs: 완료된 퀘스트 히스토리

 레벨업 커브:
 - 다음 레벨 요구 XP = floor(현재 요구 XP * 1.4)
 - Lv1→2: 100 XP / Lv2→3: 140 XP / Lv3→4: 196 XP ...
============================================================
"""

from datetime import datetime, date, timedelta
from typing import Optional
import math

from ..models.database import get_session, UserStatsDB, QuestLogDB
from ..models.schemas import (
    UserStats,
    QuestLog,
    QuestCategory,
    QuestDifficulty,
)

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


def _to_user_stats(row: UserStatsDB) -> UserStats:
    """DB 행 → Pydantic DTO 변환"""
    return UserStats(
        name=row.name,
        level=row.level,
        current_xp=row.current_xp,
        xp_to_next=row.xp_to_next,
        total_xp=row.total_xp,
        title=row.title,
        completed_count=row.completed_count,
        streak=row.streak,
        daily_streak=row.daily_streak,
        last_daily_date=row.last_daily_date,
    )


# ============================================================
#  유저 상태 관리
# ============================================================

def get_user_stats() -> UserStats:
    """
    현재 유저 상태를 DB에서 조회
    DB에 데이터가 없으면 초기 상태를 생성하여 반환
    """
    session = get_session()
    try:
        row = session.query(UserStatsDB).first()
        if not row:
            row = UserStatsDB(
                name="Player",
                level=1,
                current_xp=0,
                xp_to_next=100,
                total_xp=0,
                title="초보 모험가",
                completed_count=0,
                streak=0,
                daily_streak=0,
                last_daily_date=None,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
        return _to_user_stats(row)
    finally:
        session.close()


def update_user_name(name: str) -> UserStats:
    """닉네임 변경"""
    session = get_session()
    try:
        row = session.query(UserStatsDB).first()
        if row:
            row.name = name
            row.updated_at = datetime.now()
        else:
            row = UserStatsDB(name=name)
            session.add(row)
        session.commit()
        return get_user_stats()
    finally:
        session.close()


def grant_xp(xp_amount: int) -> tuple[UserStats, bool, Optional[int]]:
    """
    경험치 부여 및 레벨업 처리

    레벨업 로직:
        1. 현재 XP에 획득 XP를 더함
        2. 현재 XP >= 요구 XP이면 레벨업
        3. 다중 레벨업 가능 (while 루프)
    """
    session = get_session()
    try:
        row = session.query(UserStatsDB).first()
        if not row:
            # 초기 유저 생성
            get_user_stats()
            row = session.query(UserStatsDB).first()

        new_xp = row.current_xp + xp_amount
        new_total = row.total_xp + xp_amount
        new_level = row.level
        xp_to_next = row.xp_to_next
        leveled_up = False

        while new_xp >= xp_to_next:
            new_xp -= xp_to_next
            new_level += 1
            xp_to_next = math.floor(xp_to_next * 1.4)
            leveled_up = True

        row.current_xp = new_xp
        row.total_xp = new_total
        row.level = new_level
        row.xp_to_next = xp_to_next
        row.title = _get_title(new_level)
        row.completed_count = row.completed_count + 1
        row.streak = row.streak + 1
        row.updated_at = datetime.now()

        session.commit()
        session.refresh(row)

        return (
            _to_user_stats(row),
            leveled_up,
            new_level if leveled_up else None,
        )
    finally:
        session.close()


def grant_xp_only(xp_amount: int) -> tuple[UserStats, bool, Optional[int]]:
    """
    경험치만 부여 (completed_count, streak 변동 없음)
    세부 퀘스트 완료 시 사용
    """
    session = get_session()
    try:
        row = session.query(UserStatsDB).first()
        if not row:
            get_user_stats()
            row = session.query(UserStatsDB).first()

        new_xp = row.current_xp + xp_amount
        new_total = row.total_xp + xp_amount
        new_level = row.level
        xp_to_next = row.xp_to_next
        leveled_up = False

        while new_xp >= xp_to_next:
            new_xp -= xp_to_next
            new_level += 1
            xp_to_next = math.floor(xp_to_next * 1.4)
            leveled_up = True

        row.current_xp = new_xp
        row.total_xp = new_total
        row.level = new_level
        row.xp_to_next = xp_to_next
        row.title = _get_title(new_level)
        row.updated_at = datetime.now()

        session.commit()
        session.refresh(row)

        return (_to_user_stats(row), leveled_up, new_level if leveled_up else None)
    finally:
        session.close()


def complete_daily_quest(xp_amount: int) -> tuple[UserStats, bool, Optional[int], int, bool, int]:
    """
    일일 퀘스트 완료 처리 - 일일 연속 스트릭 관리

    Returns:
        (stats, level_up, new_level, daily_streak, weekly_bonus, weekly_bonus_xp)
    """
    session = get_session()
    try:
        row = session.query(UserStatsDB).first()
        if not row:
            get_user_stats()
            row = session.query(UserStatsDB).first()

        today_str = date.today().isoformat()
        new_daily_streak = row.daily_streak or 0
        last_date = row.last_daily_date

        if last_date == today_str:
            pass
        elif last_date:
            yesterday = (date.today() - timedelta(days=1)).isoformat()
            if last_date == yesterday:
                new_daily_streak += 1
            else:
                new_daily_streak = 1
        else:
            new_daily_streak = 1

        # 7일 연속 보너스
        weekly_bonus = False
        weekly_bonus_xp = 0
        if new_daily_streak > 0 and new_daily_streak % 7 == 0:
            weekly_bonus = True
            weekly_bonus_xp = 200

        # DB에 스트릭 업데이트
        row.daily_streak = new_daily_streak
        row.last_daily_date = today_str
        session.commit()
    finally:
        session.close()

    # XP 부여
    total_xp = xp_amount + weekly_bonus_xp
    updated_stats, level_up, new_level = grant_xp(total_xp)

    return (updated_stats, level_up, new_level, new_daily_streak, weekly_bonus, weekly_bonus_xp)


def reset_streak():
    """콤보 리셋 (검증 실패 시)"""
    session = get_session()
    try:
        row = session.query(UserStatsDB).first()
        if row:
            row.streak = 0
            row.updated_at = datetime.now()
            session.commit()
    finally:
        session.close()


def reset_daily_streak():
    """일일 스트릭 리셋 (자정에 미완료 퀘스트 존재 시)"""
    session = get_session()
    try:
        row = session.query(UserStatsDB).first()
        if row:
            row.daily_streak = 0
            row.updated_at = datetime.now()
            session.commit()
    finally:
        session.close()


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
    """퀘스트 완료 기록을 quest_logs 테이블에 추가"""
    session = get_session()
    try:
        log = QuestLogDB(
            quest_title=quest_title,
            category=category,
            difficulty=difficulty,
            xp_earned=xp_earned,
            ai_feedback=ai_feedback,
            completed_at=datetime.now(),
            had_proof=had_proof,
        )
        session.add(log)
        session.commit()
    finally:
        session.close()


def get_quest_logs(limit: int = 50) -> list[QuestLog]:
    """퀘스트 완료 기록을 최신순으로 조회"""
    session = get_session()
    try:
        rows = (
            session.query(QuestLogDB)
            .order_by(QuestLogDB.completed_at.desc())
            .limit(limit)
            .all()
        )

        result = []
        for row in rows:
            try:
                result.append(QuestLog(
                    quest_title=row.quest_title,
                    category=QuestCategory(row.category or "etc"),
                    difficulty=QuestDifficulty(row.difficulty or "medium"),
                    xp_earned=row.xp_earned,
                    ai_feedback=row.ai_feedback or "",
                    completed_at=row.completed_at.isoformat() if row.completed_at else "",
                    had_proof=row.had_proof or False,
                ))
            except (ValueError, AttributeError):
                continue
        return result
    finally:
        session.close()


def reset_all():
    """전체 데이터 초기화 (디버그/설정용)"""
    session = get_session()
    try:
        session.query(QuestLogDB).delete()
        session.query(UserStatsDB).delete()
        session.commit()
    finally:
        session.close()
