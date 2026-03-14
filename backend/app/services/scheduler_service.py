"""
============================================================
 스케줄러 서비스 - 일일 퀘스트 자동 리셋 + 스트릭 관리
============================================================
 APScheduler를 사용하여 매일 자정에:
 1. 미완료 일일 퀘스트 확인 → 스트릭 리셋 (엄격 모드)
 2. Daily 태그 퀘스트 완료 상태를 false로 리셋
============================================================
"""

import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from ..config import settings

logger = logging.getLogger("scheduler")

scheduler = AsyncIOScheduler()


async def _reset_daily_job():
    """
    매일 자정 실행되는 일일 퀘스트 리셋 작업

    순서:
    1. 먼저 미완료 일일 퀘스트가 있는지 확인
    2. 미완료가 있으면 daily_streak을 0으로 초기화 (엄격 모드)
    3. 일일 퀘스트 완료 상태를 모두 false로 리셋
    """
    try:
        logger.info("일일 퀘스트 자정 처리 시작...")

        # 1단계: 미완료 일일 퀘스트 확인 → 스트릭 리셋
        if settings.is_db_mode:
            from . import quest_db_service, game_service
            has_incomplete = quest_db_service.check_daily_incomplete()
            if has_incomplete:
                game_service.reset_daily_streak()
                logger.info("미완료 일일 퀘스트 발견 → daily_streak 리셋!")
            else:
                logger.info("모든 일일 퀘스트 완료됨 → 스트릭 유지")
        else:
            # 노션 모드에서도 스트릭 리셋 처리 가능
            from . import game_service
            # 노션 모드에서는 마지막 일일 퀘스트 날짜로 판단
            # (별도 구현 필요시 확장)

        # 2단계: 일일 퀘스트 완료 상태 리셋
        if settings.is_db_mode:
            from . import quest_db_service
            quest_db_service.reset_daily_quests()
        else:
            from . import notion_service
            await notion_service.reset_daily_quests()

        logger.info("일일 퀘스트 리셋 완료")
    except Exception as e:
        logger.error(f"일일 퀘스트 리셋 실패: {e}")


def start_scheduler():
    """스케줄러 시작 - FastAPI 시작 시 호출"""
    scheduler.add_job(
        _reset_daily_job,
        trigger=CronTrigger(hour=0, minute=0),  # 매일 자정
        id="daily_quest_reset",
        name="일일 퀘스트 리셋 + 스트릭 관리",
        replace_existing=True,
    )
    scheduler.start()
    mode = "DB 모드" if settings.is_db_mode else "노션 모드"
    logger.info(f"스케줄러 시작됨 ({mode}) - 매일 자정 일일 퀘스트 리셋 예약")


def stop_scheduler():
    """스케줄러 종료 - FastAPI 종료 시 호출"""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("스케줄러 종료됨")
