#!/usr/bin/env python3
import signal
import time

from dotenv import load_dotenv

from app import create_app
from app.scheduler import start_scheduler


load_dotenv()
app = create_app()
scheduler = start_scheduler(app)
_keep_running = True


def _stop_scheduler(signum, frame):
    global _keep_running
    app.logger.info(f"Received signal {signum}; shutting down scheduler worker.")
    _keep_running = False


signal.signal(signal.SIGINT, _stop_scheduler)
signal.signal(signal.SIGTERM, _stop_scheduler)

if scheduler is None:
    app.logger.error(
        "Scheduler worker did not start."
    )
    raise SystemExit(1)

app.logger.info("Scheduler worker is running.")

while _keep_running:
    time.sleep(5)
