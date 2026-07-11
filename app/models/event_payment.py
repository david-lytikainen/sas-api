from app.extensions import db


class EventPayment(db.Model):
    __tablename__ = "event_payments"

    id = db.Column(db.Integer, primary_key=True)
    stripe_checkout_session_id = db.Column(db.String(255), unique=True, nullable=False)
    stripe_payment_intent_id = db.Column(db.String(255), nullable=True)
    stripe_charge_id = db.Column(db.String(255), nullable=True)
    stripe_refund_id = db.Column(db.String(255), nullable=True)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    organizer_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    amount_cents = db.Column(db.Integer, nullable=False, default=0)
    refunded_amount_cents = db.Column(db.Integer, nullable=False, default=0)
    currency = db.Column(db.String(10), nullable=False, default="usd")
    payment_status = db.Column(db.String(50), nullable=False, default="paid")
    registration_status = db.Column(db.String(50), nullable=False, default="pending")
    refund_status = db.Column(db.String(50), nullable=True)
    failure_reason = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.TIMESTAMP(timezone=True), nullable=False, server_default=db.func.now())
    updated_at = db.Column(db.TIMESTAMP(timezone=True), nullable=False, server_default=db.func.now(), onupdate=db.func.now())
