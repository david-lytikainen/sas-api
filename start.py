#!/usr/bin/env python3
import os
from dotenv import load_dotenv
from app import create_app, db  
import app.models.event_waitlist
# Load environment variables
load_dotenv()

# Create the Flask application
app = create_app()

# Create database tables if they don't exist
with app.app_context():
    app.logger.info("Attempting to create database tables...")
    # Log known tables by SQLAlchemy metadata
    app.logger.info(f"Tables known to SQLAlchemy metadata before create_all: {list(db.metadata.tables.keys())}")
    db.create_all()
    app.logger.info("Database tables check/creation complete.")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=True)
