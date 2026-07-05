from datetime import datetime, timedelta, timezone
from flask import current_app, render_template
from flask_mail import Mail, Message
from zoneinfo import ZoneInfo

from app.extensions import db
from app.models import EmailJob, Event, User


mail = Mail()
EMAIL_TIMEZONE = ZoneInfo("America/New_York")
EMAIL_JOB_STATUS_PENDING = "pending"
EMAIL_JOB_STATUS_PROCESSING = "processing"
EMAIL_JOB_STATUS_SENT = "sent"
EMAIL_JOB_STATUS_FAILED = "failed"
EMAIL_JOB_MAX_ATTEMPTS = 3
EMAIL_JOB_RETRY_DELAY = timedelta(minutes=5)
EMAIL_JOB_SENT_RETENTION_DAYS = 30


def enqueue_email_job(job_type: str, payload: dict, scheduled_for: datetime | None = None):
    job = EmailJob(
        job_type=job_type,
        payload=payload,
        status=EMAIL_JOB_STATUS_PENDING,
        scheduled_for=scheduled_for or datetime.now(timezone.utc),
    )
    db.session.add(job)
    db.session.commit()
    return job


def process_pending_email_jobs(now_utc: datetime | None = None, limit: int = 25) -> int:
    comparison_time = now_utc or datetime.now(timezone.utc)
    jobs = (
        EmailJob.query.filter(
            EmailJob.status == EMAIL_JOB_STATUS_PENDING,
            EmailJob.scheduled_for <= comparison_time,
        )
        .order_by(EmailJob.scheduled_for.asc(), EmailJob.id.asc())
        .limit(limit)
        .all()
    )
    processed_count = 0

    for job in jobs:
        try:
            job.status = EMAIL_JOB_STATUS_PROCESSING
            job.attempts += 1
            job.last_error = None
            db.session.commit()
            _deliver_email_job(job)
            job.status = EMAIL_JOB_STATUS_SENT
            job.sent_at = datetime.now(timezone.utc)
            db.session.commit()
            processed_count += 1
        except Exception as exc:
            db.session.rollback()
            job = EmailJob.query.get(job.id)
            if not job:
                continue
            job.last_error = str(exc)
            if job.attempts >= EMAIL_JOB_MAX_ATTEMPTS:
                job.status = EMAIL_JOB_STATUS_FAILED
            else:
                job.status = EMAIL_JOB_STATUS_PENDING
                job.scheduled_for = comparison_time + EMAIL_JOB_RETRY_DELAY
            db.session.commit()
            current_app.logger.error(
                f"Failed to process email job {job.id}: {str(exc)}", exc_info=True
            )

    _purge_old_sent_email_jobs(comparison_time)
    return processed_count


def _purge_old_sent_email_jobs(now_utc: datetime):
    cutoff = now_utc - timedelta(days=EMAIL_JOB_SENT_RETENTION_DAYS)
    (
        EmailJob.query.filter(
            EmailJob.status == EMAIL_JOB_STATUS_SENT,
            EmailJob.sent_at.isnot(None),
            EmailJob.sent_at < cutoff,
        ).delete(synchronize_session=False)
    )
    db.session.commit()


def send_password_reset_email(user):
    token = user.get_reset_token()
    app = current_app._get_current_object()

    if app.testing:
        app.logger.info("--- MOCK EMAIL ---")
        app.logger.info(f"To: {user.email}")
        app.logger.info("Subject: Password Reset Request")
        app.logger.info(
            f"Body: To reset your password, visit the following link:\n"
            f"{app.config.get('CLIENT_URL')}/reset-password/{token}"
        )
        app.logger.info(f"Reset Token: {token}")
        app.logger.info("--- END MOCK EMAIL ---")
        return

    enqueue_email_job(
        "password_reset",
        {
            "user_id": user.id,
            "token": token,
        },
    )


def send_waitlist_spot_open_email(user, event):
    app = current_app._get_current_object()
    signup_url = f"{app.config.get('CLIENT_URL')}/events?view=all"

    if app.testing:
        app.logger.info("--- MOCK EMAIL ---")
        app.logger.info(f"To: {user.email}")
        app.logger.info("Subject: Saved & Single Event Spot Opened")
        app.logger.info(
            f"Body: A spot opened for {event.name}. Visit {signup_url} to sign up now."
        )
        app.logger.info("--- END MOCK EMAIL ---")
        return

    enqueue_email_job(
        "waitlist_spot_open",
        {
            "user_id": user.id,
            "event_id": event.id,
        },
    )


def send_event_registration_confirmation_email(user, event, organizer):
    app = current_app._get_current_object()
    event_url = f"{app.config.get('CLIENT_URL')}/events?view=all"
    event_time = event.starts_at.astimezone(EMAIL_TIMEZONE).strftime(
        "%A, %B %-d, %Y at %-I:%M %p %Z"
    )

    if app.testing:
        app.logger.info("--- MOCK EMAIL ---")
        app.logger.info(f"To: {user.email}")
        app.logger.info("Subject: Saved & Single Event Registration Confirmed")
        app.logger.info(
            f'Body: Registered for {event.name} on {event_time}. Open {event_url}.'
        )
        app.logger.info("--- END MOCK EMAIL ---")
        return

    enqueue_email_job(
        "registration_confirmation",
        {
            "user_id": user.id,
            "event_id": event.id,
            "organizer_id": organizer.id,
        },
    )


def send_event_reminder_email(user, event, organizer, reminder_label: str):
    app = current_app._get_current_object()
    event_url = f"{app.config.get('CLIENT_URL')}/events?view=all"
    event_time = event.starts_at.astimezone(EMAIL_TIMEZONE).strftime(
        "%A, %B %-d, %Y at %-I:%M %p %Z"
    )

    if app.testing:
        app.logger.info("--- MOCK EMAIL ---")
        app.logger.info(f"To: {user.email}")
        app.logger.info(f"Subject: Saved & Single Event Reminder ({reminder_label})")
        app.logger.info(
            f'Body: Reminder for {event.name} on {event_time}. Open {event_url}.'
        )
        app.logger.info("--- END MOCK EMAIL ---")
        return

    enqueue_email_job(
        "event_reminder",
        {
            "user_id": user.id,
            "event_id": event.id,
            "organizer_id": organizer.id,
            "reminder_label": reminder_label,
        },
    )


def _deliver_email_job(job: EmailJob):
    if job.job_type == "password_reset":
        _deliver_password_reset_email(job.payload)
        return
    if job.job_type == "waitlist_spot_open":
        _deliver_waitlist_spot_open_email(job.payload)
        return
    if job.job_type == "registration_confirmation":
        _deliver_registration_confirmation_email(job.payload)
        return
    if job.job_type == "event_reminder":
        _deliver_event_reminder_email(job.payload)
        return
    raise ValueError(f"Unsupported email job type: {job.job_type}")


def _deliver_password_reset_email(payload: dict):
    user = User.query.get(payload["user_id"])
    if not user:
        raise ValueError("Password reset email user no longer exists.")

    reset_url = f"{current_app.config.get('CLIENT_URL')}/reset-password/{payload['token']}"
    msg = Message(
        "Saved & Single Password Reset",
        sender=("Saved & Single", current_app.config.get("MAIL_USERNAME")),
        recipients=[user.email],
    )
    msg.html = render_template(
        "email/reset_password.html",
        user=user,
        reset_url=reset_url,
        current_year=datetime.utcnow().year,
    )
    mail.send(msg)


def _deliver_waitlist_spot_open_email(payload: dict):
    user = User.query.get(payload["user_id"])
    event = Event.query.get(payload["event_id"])
    if not user or not event:
        raise ValueError("Waitlist spot open email dependencies are missing.")

    signup_url = f"{current_app.config.get('CLIENT_URL')}/events?view=all"
    msg = Message(
        "A spot opened up for an event you are waitlisted on",
        sender=("Saved & Single", current_app.config.get("MAIL_USERNAME")),
        recipients=[user.email],
    )
    msg.body = (
        f"Hi {user.first_name},\n\n"
        f"A spot has opened up for \"{event.name}\" on Saved & Single.\n"
        "You are still on the waitlist, but you can go back into the site and sign up now if spots are still available.\n\n"
        f"Open the site: {signup_url}\n\n"
        "Spots are filling fast, so this is first come, first served.\n\n"
        "Saved & Single"
    )
    mail.send(msg)


def _deliver_registration_confirmation_email(payload: dict):
    user = User.query.get(payload["user_id"])
    event = Event.query.get(payload["event_id"])
    organizer = User.query.get(payload["organizer_id"])
    if not user or not event or not organizer:
        raise ValueError("Registration confirmation email dependencies are missing.")

    event_url = f"{current_app.config.get('CLIENT_URL')}/events?view=all"
    event_time = event.starts_at.astimezone(EMAIL_TIMEZONE).strftime(
        "%A, %B %-d, %Y at %-I:%M %p %Z"
    )
    organizer_name = f"{organizer.first_name} {organizer.last_name}".strip()
    msg = Message(
        "Saved & Single Registration Confirmed",
        sender=("Saved & Single", current_app.config.get("MAIL_USERNAME")),
        recipients=[user.email],
    )
    msg.body = (
        f"Hi {user.first_name},\n\n"
        f'You are registered for "{event.name}" on Saved & Single.\n\n'
        f"Event date and time: {event_time}\n"
        f"Address: {event.address}\n"
        f"Organizer: {organizer_name}\n"
        f"Organizer email: {organizer.email}\n\n"
        "If your plans change, you can cancel through the website, but refunds are not handled through the app.\n\n"
        f"Open the site: {event_url}\n\n"
        "Saved & Single"
    )
    mail.send(msg)


def _deliver_event_reminder_email(payload: dict):
    user = User.query.get(payload["user_id"])
    event = Event.query.get(payload["event_id"])
    organizer = User.query.get(payload["organizer_id"])
    if not user or not event or not organizer:
        raise ValueError("Event reminder email dependencies are missing.")

    event_url = f"{current_app.config.get('CLIENT_URL')}/events?view=all"
    event_time = event.starts_at.astimezone(EMAIL_TIMEZONE).strftime(
        "%A, %B %-d, %Y at %-I:%M %p %Z"
    )
    organizer_name = f"{organizer.first_name} {organizer.last_name}".strip()
    msg = Message(
        f"Saved & Single reminder: {event.name}",
        sender=("Saved & Single", current_app.config.get("MAIL_USERNAME")),
        recipients=[user.email],
    )
    msg.body = (
        f"Hi {user.first_name},\n\n"
        f'This is your {payload["reminder_label"]} reminder for "{event.name}" on Saved & Single.\n\n'
        f"Event date and time: {event_time}\n"
        f"Address: {event.address}\n"
        f"Organizer: {organizer_name}\n"
        f"Organizer email: {organizer.email}\n\n"
        "If your plans change, you can cancel through the website, but refunds are not handled through the app.\n\n"
        f"Open the site: {event_url}\n\n"
        "Saved & Single"
    )
    mail.send(msg)
