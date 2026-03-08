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

    # 로컬 DB 경로
    DB_PATH: str = str(Path(__file__).parent.parent / "data" / "database.json")

    model_config = {
        "env_file": str(Path(__file__).parent.parent / ".env"),
        "env_file_encoding": "utf-8",
    }


settings = Settings()
