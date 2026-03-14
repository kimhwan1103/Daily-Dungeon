"""
============================================================
 앱 설정 (환경변수 로딩)
============================================================
 .env 파일에서 API 키와 서버 설정을 로딩
 pydantic-settings를 사용하여 타입 검증 + 자동 로딩
============================================================
"""

from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    # Notion API 연동 키
    NOTION_API_KEY: str = ""
    NOTION_DATABASE_ID: str = ""

    # Gemini API 키
    GEMINI_API_KEY: str = ""

    # 서버 설정
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    # 데이터베이스 URL (SQLAlchemy 형식)
    # 기본값: 로컬 SQLite 파일
    # 예시:
    #   sqlite:///./data/quest.db          (로컬 SQLite)
    #   postgresql://user:pass@host/dbname (PostgreSQL)
    #   mysql+pymysql://user:pass@host/db  (MySQL)
    DATABASE_URL: str = "sqlite:///" + str(
        Path(__file__).parent.parent / "data" / "quest.db"
    ).replace("\\", "/")

    # SSH 터널 설정 (PostgreSQL 원격 접속 시)
    # SSH_HOST를 설정하면 자동으로 SSH 터널을 통해 DB에 연결
    SSH_HOST: str = ""
    SSH_PORT: int = 22
    SSH_USER: str = ""
    SSH_PASSWORD: str = ""
    SSH_KEY_PATH: str = ""  # SSH 키 파일 경로 (비밀번호 대신 사용 가능)
    SSH_DB_HOST: str = "127.0.0.1"  # 터널 너머 DB 호스트 (보통 127.0.0.1)
    SSH_DB_PORT: int = 5432          # 터널 너머 DB 포트

    # TinyDB 경로 (하위 호환용, DATABASE_URL 우선)
    DB_PATH: str = str(Path(__file__).parent.parent / "data" / "database.json")

    @property
    def is_db_mode(self) -> bool:
        """
        DB 모드 여부 판별
        - SQLite(기본값) → False (노션 동기화 모드)
        - PostgreSQL/MySQL 등 외부 DB → True (노션 동기화 비활성)
        """
        return not self.DATABASE_URL.startswith("sqlite")

    model_config = {
        "env_file": str(Path(__file__).parent.parent / ".env"),
        "env_file_encoding": "utf-8",
    }


settings = Settings()
