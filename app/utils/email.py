import os
from flask import current_app, render_template
from flask_mail import Message, Mail
from threading import Thread

mail = Mail()

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

    msg = Message(
        "Password Reset Request",
        sender=os.getenv("MAIL_USERNAME"),
        recipients=[user.email],
    )
    msg.body = f"""To reset your password, visit the following link:
{app.config.get('CLIENT_URL')}/reset-password/{token}

If you did not make this password reset request, please ignore this email.

Thanks!
The Saved and Single Team
"""
    Thread(target=send_async_email, args=(app, msg)).start() 