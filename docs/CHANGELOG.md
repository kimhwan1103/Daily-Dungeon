# Changelog

Quest Widget의 모든 주요 변경 사항을 기록합니다.
형식은 [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)를 따르며,
버전은 [Semantic Versioning](https://semver.org/lang/ko/)을 따릅니다.

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
