from app import create_app, db

app = create_app()
with app.app_context():
    try:
        db.engine.connect()
        print("Connected to the database successfully.")
    except Exception as e:
        print(f"Failed to connect to the database: {e}")
