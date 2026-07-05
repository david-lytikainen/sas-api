#!/usr/bin/env python3
import os
from importlib import import_module
from dotenv import load_dotenv
from app import create_app
from app.scheduler import start_embedded_scheduler

# Load environment variables
load_dotenv()

# Create the Flask application
app = create_app()
start_embedded_scheduler(app)
import_module("app.models.event_waitlist")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=True)
