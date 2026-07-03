from flask import current_app, render_template
from flask_mail import Message, Mail
from threading import Thread
from datetime import datetime
from zoneinfo import ZoneInfo

mail = Mail()
EMAIL_TIMEZONE = ZoneInfo("America/New_York")


def send_async_email(app, msg):
    with app.app_context():
        try:
            mail.send(msg)
        except Exception as e:
            app.logger.error(f"Failed to send email: {e}")


def send_password_reset_email(user):
    token = user.get_reset_token()
    app = current_app._get_current_object()

    # If in testing mode, log the email instead of sending it
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

    reset_url = f"{app.config.get('CLIENT_URL')}/reset-password/{token}"
    current_year = datetime.utcnow().year

    msg = Message(
        "Saved & Single Password Reset",
        sender=("Saved & Single", app.config.get("MAIL_USERNAME")),
        recipients=[user.email],
    )

    msg.html = render_template(
        "email/reset_password.html",
        user=user,
        reset_url=reset_url,
        current_year=current_year,
    )

    Thread(target=send_async_email, args=(app, msg)).start()


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

    msg = Message(
        "A spot opened up for an event you are waitlisted on",
        sender=("Saved & Single", app.config.get("MAIL_USERNAME")),
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

    Thread(target=send_async_email, args=(app, msg)).start()


def send_event_registration_confirmation_email(user, event, organizer):
    app = current_app._get_current_object()
    event_url = f"{app.config.get('CLIENT_URL')}/events?view=all"
    event_time = event.starts_at.astimezone(EMAIL_TIMEZONE).strftime(
        "%A, %B %-d, %Y at %-I:%M %p %Z"
    )
    organizer_name = f"{organizer.first_name} {organizer.last_name}".strip()

    if app.testing:
        app.logger.info("--- MOCK EMAIL ---")
        app.logger.info(f"To: {user.email}")
        app.logger.info("Subject: Saved & Single Event Registration Confirmed")
        app.logger.info(
            f'Body: Registered for {event.name} on {event_time}. Open {event_url}.'
        )
        app.logger.info("--- END MOCK EMAIL ---")
        return

    msg = Message(
        "Saved & Single Registration Confirmed",
        sender=("Saved & Single", app.config.get("MAIL_USERNAME")),
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

    Thread(target=send_async_email, args=(app, msg)).start()

