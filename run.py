from app import create_app
from app.scheduler import start_embedded_scheduler

app = create_app()
start_embedded_scheduler(app)

if __name__ == "__main__":
    app.run(debug=True)
