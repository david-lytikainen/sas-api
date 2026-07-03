#!/usr/bin/env python3
from datetime import datetime, timezone

from app import create_app
from app.services.event_service import EventService


def main():
    app = create_app()

    with app.app_context():
        now_utc = datetime.now(timezone.utc)
        now_est = now_utc.astimezone(EventService.AUTO_COMPLETE_TIMEZONE)

        if now_est.hour < 21:
            app.logger.info(
                "Skipping due-event reminders because current Eastern time is before 9:00 PM."
            )
            print("Skipped reminders before 9:00 PM Eastern.")
            return

        reminder_count = EventService.send_due_event_reminders(now_utc)
        app.logger.info(
            "Sent %s due event reminder(s) from 9:00 PM Eastern maintenance run.",
            reminder_count,
        )
        print(f"Sent {reminder_count} due event reminder(s).")


if __name__ == "__main__":
    main()
