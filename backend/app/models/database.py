"""
============================================================
 SQLAlchemy 데이터베이스 모델 및 엔진 설정
============================================================
 DATABASE_URL을 통해 다양한 DB 백엔드를 지원
 - sqlite:///./data/quest.db        (기본값, 로컬)
 - postgresql://user:pass@host/db   (PostgreSQL)
 - mysql+pymysql://user:pass@host/db (MySQL)

 앱 시작 시 init_db()를 호출하면 테이블이 없을 경우 자동 생성
============================================================
"""

import atexit
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Boolean,
    DateTime, Text, MetaData,
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from ..config import settings

# ============================================================
#  SSH 터널 + 엔진 & 세션 설정
# ============================================================

_ssh_tunnel = None  # 모듈 레벨에서 터널 참조 유지


def _create_engine_with_tunnel():
    """
    SSH_HOST가 설정되어 있으면 SSH 터널을 열고,
    터널의 로컬 포트를 사용하여 DB에 연결.
    SSH_HOST가 없으면 DATABASE_URL을 그대로 사용.
    """
    global _ssh_tunnel
    db_url = settings.DATABASE_URL
    connect_args = {}

    if settings.SSH_HOST:
        # SSH 터널 생성
        try:
            from sshtunnel import SSHTunnelForwarder

            tunnel_kwargs = {
                "ssh_address_or_host": (settings.SSH_HOST, settings.SSH_PORT),
                "ssh_username": settings.SSH_USER,
                "remote_bind_address": (settings.SSH_DB_HOST, settings.SSH_DB_PORT),
            }

            # 키 파일 우선, 없으면 비밀번호
            if settings.SSH_KEY_PATH:
                tunnel_kwargs["ssh_pkey"] = settings.SSH_KEY_PATH
            elif settings.SSH_PASSWORD:
                tunnel_kwargs["ssh_password"] = settings.SSH_PASSWORD

            _ssh_tunnel = SSHTunnelForwarder(**tunnel_kwargs)
            _ssh_tunnel.start()

            # DATABASE_URL의 host:port를 터널 로컬 포트로 교체
            local_port = _ssh_tunnel.local_bind_port
            import re
            db_url = re.sub(
                r"@[^/]+",
                f"@127.0.0.1:{local_port}",
                settings.DATABASE_URL,
            )

            # 종료 시 터널 정리
            atexit.register(_close_tunnel)
        except ImportError:
            import logging
            logging.getLogger("database").warning(
                "sshtunnel 패키지 미설치 - SSH 터널 없이 직접 연결합니다. "
                "SSH 터널이 필요하면: pip install sshtunnel"
            )
        except Exception as e:
            import logging
            logging.getLogger("database").warning(
                f"SSH 터널 연결 실패 - 직접 연결 시도: {e}"
            )
    elif db_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}

    return create_engine(db_url, connect_args=connect_args, echo=False)


def _close_tunnel():
    """SSH 터널 안전 종료"""
    global _ssh_tunnel
    if _ssh_tunnel and _ssh_tunnel.is_active:
        _ssh_tunnel.stop()
        _ssh_tunnel = None


engine = _create_engine_with_tunnel()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


# ============================================================
#  테이블 모델
# ============================================================

class UserStatsDB(Base):
    """유저 상태 테이블 - 레벨, XP, 칭호, 스트릭 등"""
    __tablename__ = "user_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), default="Player")
    level = Column(Integer, default=1)
    current_xp = Column(Integer, default=0)
    xp_to_next = Column(Integer, default=100)
    total_xp = Column(Integer, default=0)
    title = Column(String(50), default="초보 모험가")
    completed_count = Column(Integer, default=0)
    streak = Column(Integer, default=0)
    daily_streak = Column(Integer, default=0)
    last_daily_date = Column(String(20), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class QuestsDB(Base):
    """퀘스트 테이블 - DB 모드에서 노션 대신 사용"""
    __tablename__ = "quests"

    id = Column(String(100), primary_key=True)
    name = Column(String(500), nullable=False)
    quest_type = Column(String(20), default="sub")  # main/sub/daily
    category = Column(String(20), default="etc")
    difficulty = Column(String(20), default="medium")
    xp = Column(Integer, default=30)
    completed = Column(Boolean, default=False)
    due_date = Column(String(20), nullable=True)
    is_daily = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class SubQuestsDB(Base):
    """세부 퀘스트 테이블 - DB 모드에서 노션 to_do 블록 대신 사용"""
    __tablename__ = "sub_quests"

    id = Column(String(100), primary_key=True)
    quest_id = Column(String(100), nullable=False)  # 부모 퀘스트 ID
    text = Column(String(500), nullable=False)
    checked = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)


class QuestLogDB(Base):
    """퀘스트 완료 기록 테이블"""
    __tablename__ = "quest_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    quest_title = Column(String(500), nullable=False)
    category = Column(String(20), default="etc")
    difficulty = Column(String(20), default="medium")
    xp_earned = Column(Integer, default=0)
    ai_feedback = Column(Text, default="")
    completed_at = Column(DateTime, default=datetime.now)
    had_proof = Column(Boolean, default=False)


# ============================================================
#  DB 초기화 (테이블 자동 생성)
# ============================================================

def init_db():
    """
    데이터베이스 테이블 자동 생성 + 마이그레이션

    앱 시작 시 호출되며, 테이블이 없으면 자동으로 CREATE TABLE 실행
    이미 존재하는 테이블은 건드리지 않음 (데이터 안전)
    신규 컬럼이 추가된 경우 ALTER TABLE로 마이그레이션
    """
    Base.metadata.create_all(bind=engine)
    _migrate_quest_type()


def _migrate_quest_type():
    """quest_type 컬럼이 없는 기존 테이블에 추가"""
    from sqlalchemy import inspect, text
    insp = inspect(engine)
    if "quests" in insp.get_table_names():
        columns = [c["name"] for c in insp.get_columns("quests")]
        if "quest_type" not in columns:
            with engine.begin() as conn:
                conn.execute(text(
                    "ALTER TABLE quests ADD COLUMN quest_type VARCHAR(20) DEFAULT 'sub'"
                ))
                # is_daily=True인 기존 레코드를 daily로 변환
                conn.execute(text(
                    "UPDATE quests SET quest_type = 'daily' WHERE is_daily = true"
                ))


def get_db() -> Session:
    """FastAPI 의존성 주입용 DB 세션 팩토리"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_session() -> Session:
    """서비스 레이어에서 직접 사용하는 세션"""
    return SessionLocal()
