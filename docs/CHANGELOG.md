# Changelog

Quest Widget의 모든 주요 변경 사항을 기록합니다.
형식은 [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)를 따르며,
버전은 [Semantic Versioning](https://semver.org/lang/ko/)을 따릅니다.

---

## [1.5.0] - 2026-03-10

### Added
- **퀘스트 타입 시스템**: 3단계 퀘스트 분류 체계 도입
  - 👑 **메인 퀘스트 (Main Quest)**: 장기 핵심 목표, 기본 XP × 2.5 배율
    - 골드 글로우 UI (`#FFD700` 그라데이션 보더)
    - 완료 시 풀스크린 클리어 이펙트 (왕관 + 파티클 버스트)
    - "MAIN STORY" 섹션 상단 배치
  - ⚔️ **서브 퀘스트 (Sub Quest)**: 일반 단발성 작업 (기존 동작 유지)
    - "ACTIVE / COMPLETE" 섹션 중간 배치
  - 🔁 **일일 퀘스트 (Daily Quest)**: 반복 루틴 작업
    - 블루 쿨톤 글래스 UI (`#4FC3F7` 테마)
    - "DAILY ROUTINE" 섹션 하단 배치
    - 자정 엄격 모드: 미완료 시 `daily_streak` 즉시 리셋
- **`QuestType` 열거형**: `main` / `sub` / `daily` (Pydantic + DB 공용)
- **DB 마이그레이션**: 기존 `quests` 테이블에 `quest_type` 컬럼 자동 추가 (ALTER TABLE)
  - `is_daily = true`인 기존 퀘스트는 자동으로 `quest_type = 'daily'`로 변환

### Changed
- `index.html`: 3섹션 렌더링 (Main Story → Active/Complete → Daily Routine)
- `index.html`: 퀘스트 추가 모달에 타입 선택 버튼 (Main/Sub/Daily) 추가
- `index.html`: 메인 퀘스트 XP 라벨에 "×2.5" 접미사 표시
- `quest_db_service.py`: `_calc_xp()` 함수에 메인 퀘스트 2.5배 XP 배율 적용
- `verify.py`: AI 검증 시 `quest_type` 전달 및 메인 퀘스트 XP 배율 처리
- `schemas.py`: `QuestDTO`, `VerifyRequest`, `VerifyResponse`에 `quest_type` 필드 추가
- `scheduler_service.py`: 자정 리셋 시 미완료 일일 퀘스트 체크 → 스트릭 리셋 로직 강화
- `locales/ko.json`, `locales/en.json`: 퀘스트 타입 관련 i18n 키 추가

---

## [1.4.0] - 2026-03-10

### Added
- **DB 모드 (노션 동기화 비활성)**: 외부 DB 사용 시 노션 없이 독립 동작
  - `is_db_mode` 속성: `DATABASE_URL`이 SQLite가 아니면 자동으로 DB 모드 활성화
  - `quests`, `sub_quests` 테이블 추가 (DB 모드용 퀘스트 저장)
  - `quest_db_service.py`: DB 모드 전용 퀘스트 CRUD 서비스
  - `POST /api/quests/add` 엔드포인트 (DB 모드에서 퀘스트 직접 추가)
  - `DELETE /api/quests/{id}` 엔드포인트 (DB 모드에서 퀘스트 삭제)
  - `GET /api/mode` 엔드포인트 (현재 동작 모드 조회)

### Changed
- `quests.py`: 모든 엔드포인트가 모드에 따라 노션/DB 자동 분기
- `verify.py`: DB 모드에서 노션 완료 처리 대신 DB 업데이트
- `scheduler_service.py`: DB 모드에서 DB 기반 일일 퀘스트 리셋
- 프론트엔드: DB 모드 시 "Notion Sync" 버튼 → "퀘스트 추가" 버튼으로 변경
- 프론트엔드: 퀘스트 추가 모달 연동 (DB 모드 전용)

---

## [1.3.0] - 2026-03-10

### Added
- **다국어 지원 (i18n)**: JSON 언어팩 기반 국제화 시스템
  - `locales/ko.json` (한국어), `locales/en.json` (영어) 언어팩 추가
  - 설정 탭에서 언어 전환 가능 (선택 즉시 반영, localStorage 저장)
  - `data-i18n` 속성 기반 선언적 번역 + `t()` 함수 기반 동적 번역
  - 새 언어 추가 시 JSON 파일만 작성하면 자동 적용

### Changed
- `index.html`: 모든 하드코딩 한국어 텍스트를 i18n 키로 교체
- `package.json`: `locales/**/*` 빌드 포함 추가

---

## [1.2.0] - 2026-03-10

### Added
- **SSH 터널 지원**: 원격 PostgreSQL 등 SSH를 통한 DB 접속 지원
  - `SSH_HOST`, `SSH_PORT`, `SSH_USER`, `SSH_PASSWORD`, `SSH_KEY_PATH` 환경변수 추가
  - 앱 시작 시 자동 터널 생성, 종료 시 자동 정리 (`atexit`)
- `sshtunnel`, `psycopg2-binary` 의존성 추가

### Changed
- `database.py`: 엔진 생성 로직을 `_create_engine_with_tunnel()` 함수로 리팩터링
- `backend.spec`: `sshtunnel`, `psycopg2` hidden import 추가

---

## [1.1.0] - 2026-03-10

### Added
- **다중 DB 백엔드 지원**: SQLAlchemy 기반으로 전환
  - SQLite (기본, 로컬 파일)
  - PostgreSQL (`postgresql://...`)
  - MySQL (`mysql+pymysql://...`)
  - `DATABASE_URL` 환경변수로 DB 선택
  - 앱 시작 시 `init_db()`로 테이블 자동 생성
- **세부 퀘스트 (Sub-Quest) 시스템**
  - 노션 페이지 내부 `to_do` 블록을 세부 퀘스트로 활용
  - 진행률 프로그레스 바 표시
  - 세부 퀘스트 체크 시 +10 XP, 전체 완료 시 +100 XP 보너스
  - `POST /api/quests/sub-quest/toggle` 엔드포인트 추가
- **일일 퀘스트 (Daily Quest) 시스템**
  - 노션 `Tags` 프로퍼티에 "Daily" 태그로 자동 인식
  - APScheduler로 매일 자정 자동 리셋 (Done 체크박스 + to_do 블록 초기화)
  - AI 검증 없이 즉시 완료 처리
  - 연속 출석 스트릭 트래킹 (7일 연속 시 200 XP 보너스)
  - `POST /api/quests/{id}/daily-complete` 엔드포인트 추가
- **스케줄러 서비스**: `scheduler_service.py` (APScheduler AsyncIOScheduler)
- **FastAPI Lifespan**: DB 초기화 + 스케줄러 시작/종료 관리
- 프론트엔드: 일일 퀘스트 섹션 (파란색), 세부 퀘스트 확장 패널, 스트릭 표시 UI

### Changed
- `game_service.py`: TinyDB → SQLAlchemy ORM으로 전면 재작성
- `schemas.py`: `SubQuestDTO`, `SubQuestToggleResponse`, `DailyCompleteResponse` 등 DTO 추가
- `notion_service.py`: 세부 퀘스트 조회/토글, 일일 퀘스트 리셋 로직 추가
- `requirements.txt`: `sqlalchemy`, `aiosqlite`, `apscheduler` 추가
- `backend.spec`: 새 모듈 hidden import 추가

---

## [1.0.0] - 2026-03-09

### Added
- **데스크톱 위젯**: Electron 기반 프레임리스, 투명, 항상 위 고정 위젯
  - SAO(Sword Art Online) Utilities 스타일 UI
  - 프로스티드 글래스 패널 + 오렌지 액센트
  - 시스템 트레이 아이콘 (표시/숨기기, 클릭 무시, 종료)
  - 전역 단축키: `Ctrl+Shift+Space` (토글), `Ctrl+Shift+T` (클릭 무시)
- **노션 연동 (SSOT)**
  - 오늘 날짜 기준 퀘스트 자동 동기화
  - 카테고리(dev/study/life/work/etc), 난이도(easy/medium/hard/legendary) 매핑
  - 완료 시 노션 Done 체크박스 자동 업데이트
- **AI 검증 파이프라인**
  - Gemini AI NPC 길드마스터가 작업 증명(코드/텍스트/이미지) 평가
  - 구조화된 JSON 출력 (is_passed, confidence_score, npc_feedback)
  - 검증 통과 시 XP 부여 + 노션 상태 변경, 실패 시 콤보 리셋
  - 외부 프롬프트 관리 (`prompts/verify_prompt.json`)
- **게이미피케이션 엔진**
  - 레벨업 커브: `next_xp = floor(current_xp × 1.4)`
  - 난이도별 XP: Easy(15), Medium(30), Hard(50), Legendary(100)
  - 레벨별 칭호: 초보 모험가 → 수련생 → 전사 → 정예 기사 → 챔피언 → 전설
  - 연속 완료 콤보 트래킹
- **빌드 파이프라인**
  - PyInstaller: FastAPI 백엔드 → 단일 exe
  - electron-builder: Electron + 백엔드 → NSIS 설치 파일
  - `build.bat` 원클릭 빌드
- **API 엔드포인트**
  - `GET /api/quests/today` - 오늘의 퀘스트 동기화
  - `POST /api/quests/{id}/complete` - 퀘스트 완료 (노션 반영)
  - `POST /api/verify` - AI 작업 증명 검증
  - `GET /api/user/stats` - 유저 레벨/XP 조회
  - `PUT /api/user/name` - 닉네임 변경
  - `GET /api/history` - 완료 퀘스트 히스토리
  - `POST /api/user/reset` - 전체 데이터 초기화
