"""
Scheduler Module

Background job scheduler for automated sync operations.
Uses APScheduler to run sync jobs on configurable intervals.
"""

import os
import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.sync import sync_employees, sync_repair_orders

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration from environment
SYNC_ENABLED = os.getenv("SYNC_ENABLED", "true").lower() == "true"
TM_SHOP_ID = int(os.getenv("TM_SHOP_ID", "6212"))

# Sync intervals (configurable via env vars)
RO_SYNC_INTERVAL_MINUTES = int(os.getenv("RO_SYNC_INTERVAL_MINUTES", "10"))
EMPLOYEE_SYNC_HOUR = int(os.getenv("EMPLOYEE_SYNC_HOUR", "6"))  # 6 AM daily

# Create scheduler
scheduler = AsyncIOScheduler()


async def scheduled_employee_sync():
    """Run employee sync (daily)"""
    if not SYNC_ENABLED:
        logger.info("[Scheduler] Sync disabled, skipping employee sync")
        return

    logger.info(f"[Scheduler] Starting daily employee sync for shop {TM_SHOP_ID}")
    try:
        result = await sync_employees(TM_SHOP_ID, store_raw=False)
        logger.info(f"[Scheduler] Employee sync complete: {result.get('status')} - "
                   f"fetched={result.get('fetched', 0)}, created={result.get('created', 0)}")
    except Exception as e:
        logger.error(f"[Scheduler] Employee sync failed: {e}")


async def scheduled_ro_sync():
    """Run repair order sync (every N minutes)"""
    if not SYNC_ENABLED:
        logger.info("[Scheduler] Sync disabled, skipping RO sync")
        return

    logger.info(f"[Scheduler] Starting incremental RO sync for shop {TM_SHOP_ID}")
    try:
        # Sync POSTED ROs from last 1 day (incremental)
        result = await sync_repair_orders(
            tm_shop_id=TM_SHOP_ID,
            days_back=1,
            board="POSTED",
            store_raw=False,
            limit=None
        )
        logger.info(f"[Scheduler] RO sync complete: {result.get('status')} - "
                   f"fetched={result.get('fetched', 0)}, created={result.get('created', 0)}, "
                   f"jobs={result.get('child_entities', {}).get('jobs_created', 0)}")
    except Exception as e:
        logger.error(f"[Scheduler] RO sync failed: {e}")


async def scheduled_active_ro_sync():
    """Run active (WIP) repair order sync (every N minutes)"""
    if not SYNC_ENABLED:
        return

    logger.info(f"[Scheduler] Starting ACTIVE RO sync for shop {TM_SHOP_ID}")
    try:
        result = await sync_repair_orders(
            tm_shop_id=TM_SHOP_ID,
            days_back=7,  # Active ROs can be older
            board="ACTIVE",
            store_raw=False,
            limit=None
        )
        logger.info(f"[Scheduler] Active RO sync complete: {result.get('status')} - "
                   f"fetched={result.get('fetched', 0)}")
    except Exception as e:
        logger.error(f"[Scheduler] Active RO sync failed: {e}")


def start_scheduler():
    """Start the background scheduler"""
    if not SYNC_ENABLED:
        logger.info("[Scheduler] Sync disabled via SYNC_ENABLED env var")
        return

    logger.info(f"[Scheduler] Starting scheduler with:")
    logger.info(f"  - Employee sync: daily at {EMPLOYEE_SYNC_HOUR}:00 UTC")
    logger.info(f"  - RO sync (POSTED): every {RO_SYNC_INTERVAL_MINUTES} minutes")
    logger.info(f"  - RO sync (ACTIVE): every {RO_SYNC_INTERVAL_MINUTES} minutes (offset)")
    logger.info(f"  - Shop ID: {TM_SHOP_ID}")

    # Daily employee sync at configured hour (UTC)
    scheduler.add_job(
        scheduled_employee_sync,
        CronTrigger(hour=EMPLOYEE_SYNC_HOUR, minute=0),
        id="employee_sync",
        name="Daily Employee Sync",
        replace_existing=True
    )

    # POSTED RO sync every N minutes
    scheduler.add_job(
        scheduled_ro_sync,
        IntervalTrigger(minutes=RO_SYNC_INTERVAL_MINUTES),
        id="ro_sync_posted",
        name="Incremental POSTED RO Sync",
        replace_existing=True
    )

    # ACTIVE RO sync every N minutes (offset by half interval)
    scheduler.add_job(
        scheduled_active_ro_sync,
        IntervalTrigger(minutes=RO_SYNC_INTERVAL_MINUTES, start_date="2025-01-01 00:05:00"),
        id="ro_sync_active",
        name="Incremental ACTIVE RO Sync",
        replace_existing=True
    )

    scheduler.start()
    logger.info("[Scheduler] Scheduler started successfully")


def stop_scheduler():
    """Stop the scheduler"""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("[Scheduler] Scheduler stopped")
