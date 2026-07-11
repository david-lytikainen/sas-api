CREATE TABLE IF NOT EXISTS event_payments (
    id SERIAL PRIMARY KEY,
    stripe_checkout_session_id VARCHAR(255) NOT NULL UNIQUE,
    stripe_payment_intent_id VARCHAR(255),
    stripe_charge_id VARCHAR(255),
    stripe_refund_id VARCHAR(255),
    event_id INTEGER NOT NULL REFERENCES events(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    organizer_user_id INTEGER NOT NULL REFERENCES users(id),
    amount_cents INTEGER NOT NULL DEFAULT 0,
    refunded_amount_cents INTEGER NOT NULL DEFAULT 0,
    currency VARCHAR(10) NOT NULL DEFAULT 'usd',
    payment_status VARCHAR(50) NOT NULL DEFAULT 'paid',
    registration_status VARCHAR(50) NOT NULL DEFAULT 'pending',
    refund_status VARCHAR(50),
    failure_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS scheduler_job_runs (
    id SERIAL PRIMARY KEY,
    job_name VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL,
    processed_count INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
