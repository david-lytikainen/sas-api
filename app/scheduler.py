import atexit
import os
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Callable, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import text

from app.extensions import db
from app.models import SchedulerJobRun
from app.services.event_service import EventService
from app.utils.email import process_pending_email_jobs


_scheduler_lock = Lock()
_scheduler: Optional[BackgroundScheduler] = None
_AUTO_COMPLETE_LOCK_KEY = 90412025
_REMINDER_LOCK_KEY = 90412026
_EMAIL_JOBS_LOCK_KEY = 90412027
_EMPTY_RUN_RETENTION_DAYS = 10


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
        scheduler.add_job(
            _run_due_event_reminders,
            CronTrigger(hour=21, minute=0),
            args=[app],
            id="send-due-event-reminders",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
            misfire_grace_time=60 * 60,
        )
        scheduler.add_job(
            _run_pending_email_jobs,
            "interval",
            seconds=15,
            args=[app],
            id="process-pending-email-jobs",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
            misfire_grace_time=30,
        )
        scheduler.start()
        atexit.register(_shutdown_scheduler)
        _scheduler = scheduler
        app.extensions["embedded_scheduler"] = scheduler
        app.logger.info(
            "Embedded scheduler started for the daily 9:00 AM auto-complete and 9:00 PM reminder jobs in Eastern time."
        )
        return scheduler


def _is_werkzeug_parent_process() -> bool:
    return (
        os.getenv("FLASK_ENV") == "development"
        and os.getenv("WERKZEUG_RUN_MAIN") != "true"
    )


def _run_due_event_auto_complete(app):
    _run_locked_job(
        app,
        _AUTO_COMPLETE_LOCK_KEY,
        "Skipped due-event auto-complete because another app process holds the scheduler lock.",
        "auto-complete-due-events",
        "Embedded scheduler auto-completed %s due event(s).",
        "Embedded scheduler failed during due-event auto-complete: %s",
        lambda: EventService.auto_complete_due_events(datetime.now(timezone.utc)),
    )


def _run_due_event_reminders(app):
    _run_locked_job(
        app,
        _REMINDER_LOCK_KEY,
        "Skipped due-event reminders because another app process holds the scheduler lock.",
        "send-due-event-reminders",
        "Embedded scheduler sent %s due event reminder(s).",
        "Embedded scheduler failed during due-event reminders: %s",
        lambda: EventService.send_due_event_reminders(datetime.now(timezone.utc)),
    )


def _run_pending_email_jobs(app):
    _run_locked_job(
        app,
        _EMAIL_JOBS_LOCK_KEY,
        "Skipped pending email processing because another app process holds the scheduler lock.",
        "process-pending-email-jobs",
        "Embedded scheduler processed %s email job(s).",
        "Embedded scheduler failed during pending email processing: %s",
        lambda: process_pending_email_jobs(datetime.now(timezone.utc)),
    )


def _run_locked_job(app, lock_key: int, skip_message: str, job_name: str, success_log: str, failure_log: str, runner: Callable[[], int]):
    with app.app_context():
        lock_connection = _acquire_job_lock(lock_key)
        if lock_connection is None:
            app.logger.info(skip_message)
            return

        try:
            processed_count = runner()
            _record_scheduler_job_run(job_name, "success", processed_count)
            app.logger.info(success_log, processed_count)
        except Exception as exc:
            _record_scheduler_job_run(job_name, "failed", 0, str(exc))
            app.logger.error(failure_log, str(exc), exc_info=True)
            raise
        finally:
            _release_job_lock(lock_connection, lock_key)


def _acquire_job_lock(lock_key: int):
    if db.engine.dialect.name != "postgresql":
        return True

    connection = db.engine.connect()
    lock_acquired = connection.execute(
        text("SELECT pg_try_advisory_lock(:lock_key)"),
        {"lock_key": lock_key},
    ).scalar()
    if lock_acquired:
        return connection

    connection.close()
    return None


def _release_job_lock(lock_connection, lock_key: int):
    if lock_connection is True:
        return

    try:
        lock_connection.execute(
            text("SELECT pg_advisory_unlock(:lock_key)"),
            {"lock_key": lock_key},
        )
    finally:
        lock_connection.close()


def _shutdown_scheduler():
    global _scheduler

    with _scheduler_lock:
        if _scheduler and _scheduler.running:
            _scheduler.shutdown(wait=False)
        _scheduler = None


def _record_scheduler_job_run(
    job_name: str, status: str, processed_count: int, error_message: str | None = None
):
    try:
        db.session.add(
            SchedulerJobRun(
                job_name=job_name,
                status=status,
                processed_count=processed_count,
                error_message=error_message,
            )
        )
        db.session.commit()
        _purge_old_empty_scheduler_runs()
    except Exception:
        db.session.rollback()


def _purge_old_empty_scheduler_runs():
    cutoff = datetime.now(timezone.utc) - timedelta(days=_EMPTY_RUN_RETENTION_DAYS)
    (
        SchedulerJobRun.query.filter(
            SchedulerJobRun.status == "success",
            SchedulerJobRun.processed_count == 0,
            SchedulerJobRun.error_message.is_(None),
            SchedulerJobRun.created_at < cutoff,
        ).delete(synchronize_session=False)
    )
    db.session.commit()
