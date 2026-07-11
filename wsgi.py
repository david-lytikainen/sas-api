from app import create_app
from app.scheduler import start_embedded_scheduler

application = create_app()
start_embedded_scheduler(application)

if __name__ == "__main__":
    application.run()
