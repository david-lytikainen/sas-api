from datetime import datetime, timedelta, timezone
from typing import Callable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.extensions import db
from app.models import SchedulerJobRun
from app.services.event_service import EventService
from app.utils.email import process_pending_email_jobs


_EMPTY_RUN_RETENTION_DAYS = 10
_EMAIL_JOB_INTERVAL_SECONDS = 15 * 60


def start_scheduler(app):
    if app.testing:
        return None

    scheduler = BackgroundScheduler(timezone=str(EventService.AUTO_COMPLETE_TIMEZONE))
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
        seconds=_EMAIL_JOB_INTERVAL_SECONDS,
        args=[app],
        id="process-pending-email-jobs",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        misfire_grace_time=_EMAIL_JOB_INTERVAL_SECONDS,
    )
    scheduler.start()
    app.logger.info("Scheduler worker started.")
    return scheduler


def _run_due_event_auto_complete(app):
    _run_job(
        app,
        "auto-complete-due-events",
        "Scheduler worker auto-completed %s due event(s).",
        "Scheduler worker failed during due-event auto-complete: %s",
        lambda: EventService.auto_complete_due_events(datetime.now(timezone.utc)),
    )


def _run_due_event_reminders(app):
    _run_job(
        app,
        "send-due-event-reminders",
        "Scheduler worker sent %s due event reminder(s).",
        "Scheduler worker failed during due-event reminders: %s",
        lambda: EventService.send_due_event_reminders(datetime.now(timezone.utc)),
    )


def _run_pending_email_jobs(app):
    _run_job(
        app,
        "process-pending-email-jobs",
        "Scheduler worker processed %s email job(s).",
        "Scheduler worker failed during pending email processing: %s",
        lambda: process_pending_email_jobs(datetime.now(timezone.utc)),
    )


def _run_job(
    app,
    job_name: str,
    success_log: str,
    failure_log: str,
    runner: Callable[[], int],
):
    with app.app_context():
        try:
            processed_count = runner()
            _record_scheduler_job_run(job_name, "success", processed_count)
            app.logger.info(success_log, processed_count)
        except Exception as exc:
            _record_scheduler_job_run(job_name, "failed", 0, str(exc))
            app.logger.error(failure_log, str(exc), exc_info=True)
            raise


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
