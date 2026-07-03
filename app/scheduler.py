import atexit
import os
from datetime import datetime, timezone
from threading import Lock
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import text

from app.extensions import db
from app.services.event_service import EventService


_scheduler_lock = Lock()
_scheduler: Optional[BackgroundScheduler] = None
_JOB_LOCK_KEY = 90412025


def start_embedded_scheduler(app):
    global _scheduler

    if app.testing:
        return None

    if os.getenv("ENABLE_EMBEDDED_SCHEDULER", "true").lower() not in {
        "1",
        "true",
        "t",
        "yes",
        "on",
    }:
        app.logger.info("Embedded scheduler is disabled by environment.")
        return None

    if _is_werkzeug_parent_process():
        app.logger.info("Skipping embedded scheduler in Werkzeug reloader parent.")
        return None

    with _scheduler_lock:
        if _scheduler and _scheduler.running:
            return _scheduler

        scheduler = BackgroundScheduler(
            timezone=str(EventService.AUTO_COMPLETE_TIMEZONE)
        )
        scheduler.add_job(
            _run_due_event_auto_complete,
            CronTrigger(hour=9, minute=0),
            args=[app],
            id="auto-complete-due-events",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
            misfire_grace_time=60 * 60,
        )
        scheduler.start()
        atexit.register(_shutdown_scheduler)
        _scheduler = scheduler
        app.extensions["embedded_scheduler"] = scheduler
        app.logger.info(
            "Embedded scheduler started for daily 9:00 AM Eastern due-event auto-complete."
        )
        return scheduler


def _is_werkzeug_parent_process() -> bool:
    return (
        os.getenv("FLASK_ENV") == "development"
        and os.getenv("WERKZEUG_RUN_MAIN") != "true"
    )


def _run_due_event_auto_complete(app):
    with app.app_context():
        lock_connection = _acquire_job_lock()
        if lock_connection is None:
            app.logger.info(
                "Skipped due-event auto-complete because another app process holds the scheduler lock."
            )
            return

        try:
            completed_count = EventService.auto_complete_due_events(
                datetime.now(timezone.utc)
            )
            app.logger.info(
                "Embedded scheduler auto-completed %s due event(s).",
                completed_count,
            )
        finally:
            _release_job_lock(lock_connection)


def _acquire_job_lock():
    if db.engine.dialect.name != "postgresql":
        return True

    connection = db.engine.connect()
    lock_acquired = connection.execute(
        text("SELECT pg_try_advisory_lock(:lock_key)"),
        {"lock_key": _JOB_LOCK_KEY},
    ).scalar()
    if lock_acquired:
        return connection

    connection.close()
    return None


def _release_job_lock(lock_connection):
    if lock_connection is True:
        return

    try:
        lock_connection.execute(
            text("SELECT pg_advisory_unlock(:lock_key)"),
            {"lock_key": _JOB_LOCK_KEY},
        )
    finally:
        lock_connection.close()


def _shutdown_scheduler():
    global _scheduler

    with _scheduler_lock:
        if _scheduler and _scheduler.running:
            _scheduler.shutdown(wait=False)
        _scheduler = None
