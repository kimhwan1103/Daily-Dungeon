"""
============================================================
 DB 모드 퀘스트 서비스
============================================================
 외부 DB(PostgreSQL/MySQL) 사용 시 노션 대신
 DB에서 직접 퀘스트를 관리하는 CRUD 서비스

 퀘스트 타입:
 - main: 메인 퀘스트 (장기 목표, XP 2.5배)
 - sub: 서브 퀘스트 (일반 단발성)
 - daily: 일일 반복 퀘스트 (스트릭 연동)
============================================================
"""

import uuid
from datetime import date, datetime
from typing import Optional

from ..config import settings
from ..models.database import get_session, QuestsDB, SubQuestsDB
from ..models.schemas import QuestDTO, QuestType, QuestCategory, QuestDifficulty, SubQuestDTO

# 난이도별 XP 매핑
DIFFICULTY_XP = {
    "easy": 15,
    "medium": 30,
    "hard": 50,
    "legendary": 100,
}

# 메인 퀘스트 XP 배율
MAIN_QUEST_XP_MULTIPLIER = 2.5


def _calc_xp(difficulty: str, quest_type: str) -> int:
    """난이도 + 퀘스트 타입에 따른 XP 계산"""
    base_xp = DIFFICULTY_XP.get(difficulty, 30)
    if quest_type == "main":
        return round(base_xp * MAIN_QUEST_XP_MULTIPLIER)
    return base_xp


def fetch_all_quests() -> list[QuestDTO]:
    """
    DB에서 오늘의 퀘스트 목록 조회
    - 미완료 퀘스트 + 오늘 날짜 퀘스트
    """
    session = get_session()
    try:
        today_str = date.today().isoformat()
        rows = (
            session.query(QuestsDB)
            .filter(
                (QuestsDB.completed == False) | (QuestsDB.due_date == today_str)
            )
            .order_by(QuestsDB.created_at.asc())
            .all()
        )

        quests = []
        for row in rows:
            # 세부 퀘스트 조회
            sub_rows = (
                session.query(SubQuestsDB)
                .filter(SubQuestsDB.quest_id == row.id)
                .all()
            )
            sub_quests = [
                SubQuestDTO(block_id=sr.id, text=sr.text, checked=sr.checked)
                for sr in sub_rows
            ]

            try:
                category = QuestCategory(row.category or "etc")
            except ValueError:
                category = QuestCategory.ETC
            try:
                difficulty = QuestDifficulty(row.difficulty or "medium")
            except ValueError:
                difficulty = QuestDifficulty.MEDIUM

            # quest_type 결정 (하위 호환)
            qt = row.quest_type or ("daily" if row.is_daily else "sub")
            try:
                quest_type = QuestType(qt)
            except ValueError:
                quest_type = QuestType.SUB

            quests.append(QuestDTO(
                id=row.id,
                name=row.name,
                quest_type=quest_type,
                category=category,
                difficulty=difficulty,
                xp=_calc_xp(row.difficulty, qt),
                completed=row.completed,
                due_date=row.due_date,
                is_daily=(qt == "daily"),
                sub_quests=sub_quests,
                sub_total=len(sub_quests),
                sub_done=sum(1 for sq in sub_quests if sq.checked),
            ))
        return quests
    finally:
        session.close()


def add_quest(
    name: str,
    category: str = "etc",
    difficulty: str = "medium",
    quest_type: str = "sub",
    is_daily: bool = False,
) -> QuestDTO:
    """새 퀘스트를 DB에 추가"""
    session = get_session()
    try:
        quest_id = str(uuid.uuid4())
        # quest_type이 daily이면 is_daily도 True로 설정
        if quest_type == "daily":
            is_daily = True
        xp = _calc_xp(difficulty, quest_type)

        row = QuestsDB(
            id=quest_id,
            name=name,
            quest_type=quest_type,
            category=category,
            difficulty=difficulty,
            xp=xp,
            completed=False,
            due_date=date.today().isoformat(),
            is_daily=is_daily,
        )
        session.add(row)
        session.commit()

        return QuestDTO(
            id=quest_id,
            name=name,
            quest_type=QuestType(quest_type),
            category=QuestCategory(category),
            difficulty=QuestDifficulty(difficulty),
            xp=xp,
            completed=False,
            due_date=date.today().isoformat(),
            is_daily=is_daily,
        )
    finally:
        session.close()


def mark_complete(quest_id: str) -> bool:
    """퀘스트를 완료 처리"""
    session = get_session()
    try:
        row = session.query(QuestsDB).filter(QuestsDB.id == quest_id).first()
        if not row:
            return False
        row.completed = True
        row.updated_at = datetime.now()
        session.commit()
        return True
    finally:
        session.close()


def get_quest_type(quest_id: str) -> str:
    """퀘스트 타입 조회"""
    session = get_session()
    try:
        row = session.query(QuestsDB).filter(QuestsDB.id == quest_id).first()
        if not row:
            return "sub"
        return row.quest_type or ("daily" if row.is_daily else "sub")
    finally:
        session.close()


def toggle_sub_quest(block_id: str, checked: bool) -> bool:
    """세부 퀘스트 체크 토글"""
    session = get_session()
    try:
        row = session.query(SubQuestsDB).filter(SubQuestsDB.id == block_id).first()
        if not row:
            return False
        row.checked = checked
        session.commit()
        return True
    finally:
        session.close()


def fetch_sub_quests(quest_id: str) -> list[SubQuestDTO]:
    """퀘스트의 세부 퀘스트 목록 조회"""
    session = get_session()
    try:
        rows = (
            session.query(SubQuestsDB)
            .filter(SubQuestsDB.quest_id == quest_id)
            .all()
        )
        return [
            SubQuestDTO(block_id=r.id, text=r.text, checked=r.checked)
            for r in rows
        ]
    finally:
        session.close()


def reset_daily_quests():
    """일일 퀘스트 리셋 (DB 모드)"""
    session = get_session()
    try:
        daily_quests = (
            session.query(QuestsDB)
            .filter(
                (QuestsDB.quest_type == "daily") | (QuestsDB.is_daily == True)
            )
            .all()
        )
        for quest in daily_quests:
            quest.completed = False
            quest.updated_at = datetime.now()
            # 세부 퀘스트도 리셋
            sub_quests = (
                session.query(SubQuestsDB)
                .filter(SubQuestsDB.quest_id == quest.id)
                .all()
            )
            for sq in sub_quests:
                sq.checked = False
        session.commit()
    finally:
        session.close()


def check_daily_incomplete() -> bool:
    """미완료 일일 퀘스트 존재 여부 확인 (스트릭 리셋 판단용)"""
    session = get_session()
    try:
        incomplete = (
            session.query(QuestsDB)
            .filter(
                (QuestsDB.quest_type == "daily") | (QuestsDB.is_daily == True),
                QuestsDB.completed == False,
            )
            .count()
        )
        return incomplete > 0
    finally:
        session.close()


def delete_quest(quest_id: str) -> bool:
    """퀘스트 삭제"""
    session = get_session()
    try:
        # 세부 퀘스트 먼저 삭제
        session.query(SubQuestsDB).filter(SubQuestsDB.quest_id == quest_id).delete()
        result = session.query(QuestsDB).filter(QuestsDB.id == quest_id).delete()
        session.commit()
        return result > 0
    finally:
        session.close()
