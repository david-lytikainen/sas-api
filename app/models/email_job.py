from app.extensions import db


class EmailJob(db.Model):
    __tablename__ = "email_jobs"

    id = db.Column(db.Integer, primary_key=True)
    job_type = db.Column(db.String(64), nullable=False)
    payload = db.Column(db.JSON, nullable=False)
    status = db.Column(db.String(32), nullable=False, default="pending")
    scheduled_for = db.Column(db.TIMESTAMP(timezone=True), nullable=False, server_default=db.func.now())
    sent_at = db.Column(db.TIMESTAMP(timezone=True), nullable=True)
    last_error = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.TIMESTAMP(timezone=True), nullable=False, server_default=db.func.now())
    updated_at = db.Column(db.TIMESTAMP(timezone=True), nullable=False, server_default=db.func.now(), onupdate=db.func.now())
