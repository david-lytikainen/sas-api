import os
from flask import current_app, render_template
from flask_mail import Message, Mail
from threading import Thread
from datetime import datetime

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


def send_waitlist_opportunity_email(user, event, payment_intent_id):
    """Send email notification when a waitlist spot opens up for a paid event"""
    app = current_app._get_current_object()
    
    # If in testing mode, log the email instead of sending it
    if app.testing:
        app.logger.info("--- MOCK WAITLIST EMAIL ---")
        app.logger.info(f"To: {user.email}")
        app.logger.info(f"Subject: Spot Available - {event.name}")
        app.logger.info(f"Event: {event.name}")
        app.logger.info(f"Price: ${event.price_per_person}")
        app.logger.info(f"PaymentIntent ID: {payment_intent_id}")
        app.logger.info(f"Payment URL: {app.config.get('CLIENT_URL')}/events/{event.id}/payment?payment_intent={payment_intent_id}")
        app.logger.info("Body: A spot has opened up! You have 24 hours to complete payment.")
        app.logger.info("--- END MOCK WAITLIST EMAIL ---")
        return

    # For production, you would create an HTML email template and send it
    payment_url = f"{app.config.get('CLIENT_URL')}/events/{event.id}/payment?payment_intent={payment_intent_id}"
    
    msg = Message(
        f"Spot Available - {event.name}",
        sender=("Saved & Single", app.config.get("MAIL_USERNAME")),
        recipients=[user.email],
    )

    # Simple text email for now - you'd want to create an HTML template
    msg.body = f"""
Good news, {user.first_name}!

A spot has opened up for "{event.name}" and you're next on the waitlist!

Event Details:
- Date: {event.starts_at.strftime('%B %d, %Y at %I:%M %p')}
- Location: {event.address}
- Price: ${event.price_per_person}

You have 24 hours to complete your payment to secure your spot.

Complete Payment: {payment_url}

If you don't complete payment within 24 hours, the spot will be offered to the next person on the waitlist.

Thanks!
The Saved & Single Team
"""

    Thread(target=send_async_email, args=(app, msg)).start()


def send_waitlist_to_event_notification(user, event):
    """Send email notification when a user moves from waitlist to event registration with pending payment"""
    app = current_app._get_current_object()
    
    # If in testing mode, log the email instead of sending it
    if app.testing:
        app.logger.info("--- MOCK WAITLIST TO EVENT EMAIL ---")
        app.logger.info(f"To: {user.email}")
        app.logger.info(f"Subject: You're Registered! - {event.name}")
        app.logger.info(f"Event: {event.name}")
        app.logger.info(f"Price: ${event.price_per_person}")
        app.logger.info("Body: You've been moved from waitlist to registered! You'll pay at the event.")
        app.logger.info("--- END MOCK WAITLIST TO EVENT EMAIL ---")
        return

    msg = Message(
        f"You're Registered! - {event.name}",
        sender=("Saved & Single", app.config.get("MAIL_USERNAME")),
        recipients=[user.email],
    )

    # Simple text email for now - you'd want to create an HTML template
    msg.body = f"""
Great news, {user.first_name}!

You've been moved from the waitlist and are now registered for "{event.name}"!

Event Details:
- Date: {event.starts_at.strftime('%B %d, %Y at %I:%M %p')}
- Location: {event.address}
- Price: ${event.price_per_person}

Important: You will pay the event fee (${event.price_per_person}) when you arrive at the event. Please bring cash or a card for payment.

Your registration is confirmed, and we look forward to seeing you there!

Thanks!
The Saved & Single Team
"""

    Thread(target=send_async_email, args=(app, msg)).start()
