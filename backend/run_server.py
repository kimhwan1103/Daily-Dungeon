"""
PyInstaller로 빌드할 백엔드 진입점
단독 실행 가능한 uvicorn 서버
"""
import sys
import os

# PyInstaller 빌드 시 리소스 경로 보정
if getattr(sys, 'frozen', False):
    # exe로 실행 중일 때: exe가 있는 디렉토리를 기준으로 설정
    os.chdir(os.path.dirname(sys.executable))

import uvicorn
from app.main import app

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
