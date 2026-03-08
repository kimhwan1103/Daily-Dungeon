# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec 파일 - FastAPI 백엔드를 exe로 빌드

import os

block_cipher = None

# 프롬프트 JSON 등 데이터 파일 포함
datas = [
    ('app/prompts', 'app/prompts'),
    ('.env', '.'),
    ('data', 'data'),
]

a = Analysis(
    ['run_server.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'uvicorn.lifespan.off',
        'app.routers.quests',
        'app.routers.verify',
        'app.routers.user',
        'app.services.notion_service',
        'app.services.gemini_service',
        'app.services.game_service',
        'app.config',
        'app.models.schemas',
        'tinydb',
        'httpx',
        'google.genai',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='quest-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # 콘솔 창 숨기기
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name='quest-backend',
)
