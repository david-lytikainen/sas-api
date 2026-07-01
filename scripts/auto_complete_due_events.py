#!/usr/bin/env python3
from app import create_app
from app.services.event_service import EventService


def main():
    app = create_app()

    with app.app_context():
        completed_count = EventService.auto_complete_due_events()
        app.logger.info(
            "Auto-completed %s due event(s) from scheduled maintenance run.",
            completed_count,
        )
        print(f"Auto-completed {completed_count} due event(s).")


if __name__ == "__main__":
    main()
