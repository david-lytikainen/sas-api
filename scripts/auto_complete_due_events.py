#!/usr/bin/env python3
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from app import create_app
from app.services.event_service import EventService

AUTO_COMPLETE_TIMEZONE = ZoneInfo("America/New_York")


def main():
    app = create_app()

    with app.app_context():
        now_utc = datetime.now(timezone.utc)
        now_est = now_utc.astimezone(AUTO_COMPLETE_TIMEZONE)

        if now_est.hour < 9:
            app.logger.info(
                "Skipping due-event auto-complete because current Eastern time is before 9:00 AM."
            )
            print("Skipped auto-complete before 9:00 AM Eastern.")
            return

        completed_count = EventService.auto_complete_due_events(now_utc)
        app.logger.info(
            "Auto-completed %s due event(s) from 9:00 AM Eastern maintenance run.",
            completed_count,
        )
        print(f"Auto-completed {completed_count} due event(s).")


if __name__ == "__main__":
    main()
