"""
============================================================
 4. 스케줄러 서비스 - 일일 퀘스트 자동 리셋
============================================================
 APScheduler를 사용하여 매일 자정에 Daily 태그 퀘스트를 리셋
 - 노션의 Done 체크박스를 false로 되돌림
 - 세부 퀘스트(to_do 블록)도 함께 리셋
============================================================
"""

import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger("scheduler")

scheduler = AsyncIOScheduler()


async def _reset_daily_job():
    """매일 자정 실행되는 일일 퀘스트 리셋 작업"""
    from . import notion_service
    try:
        logger.info("일일 퀘스트 리셋 시작...")
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
        name="일일 퀘스트 리셋",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("스케줄러 시작됨 - 매일 자정 일일 퀘스트 리셋 예약")


def stop_scheduler():
    """스케줄러 종료 - FastAPI 종료 시 호출"""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("스케줄러 종료됨")
