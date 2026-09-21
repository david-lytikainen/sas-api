-- Saved & Single database schema. Safe to run on a new or existing database.

DO $$
BEGIN
    CREATE TYPE gender AS ENUM ('MALE', 'FEMALE');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    CREATE TYPE registrationstatus AS ENUM ('REGISTERED', 'CHECKED_IN', 'CANCELLED', 'WAITLISTED');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS roles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    permission_level INTEGER NOT NULL
);

INSERT INTO roles (id, name, permission_level)
VALUES (1, 'Attendee', 1), (2, 'Event Organizer', 2), (3, 'Admin', 3)
ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS churches (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    address VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS denominations (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    role_id INTEGER NOT NULL REFERENCES roles(id),
    email VARCHAR(255) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    reset_token VARCHAR(255) UNIQUE,
    reset_token_expiration TIMESTAMPTZ,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    phone VARCHAR(20) NOT NULL,
    gender gender NOT NULL,
    birthday DATE NOT NULL,
    church_id INTEGER REFERENCES churches(id),
    denomination_id INTEGER REFERENCES denominations(id),
    stripe_customer_id VARCHAR(255),
    stripe_connected_account_id VARCHAR(255),
    stripe_connect_onboarding_complete BOOLEAN,
    faith_importance INTEGER,
    traditional_roles_importance INTEGER,
    boundaries_importance INTEGER,
    looks_importance INTEGER,
    wants_kids INTEGER,
    age_gap INTEGER,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS events (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    creator_id INTEGER NOT NULL REFERENCES users(id),
    starts_at TIMESTAMPTZ NOT NULL,
    address VARCHAR(255) NOT NULL,
    max_capacity INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL,
    enforce_gender_balance BOOLEAN NOT NULL DEFAULT TRUE,
    price_per_person DECIMAL(10, 2) NOT NULL,
    registration_deadline TIMESTAMPTZ NOT NULL,
    num_rounds INTEGER,
    num_tables INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS events_attendees (
    id SERIAL PRIMARY KEY,
    event_id INTEGER NOT NULL REFERENCES events(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    status registrationstatus NOT NULL,
    pin VARCHAR(4),
    registration_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    check_in_date TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS events_organizers (
    id SERIAL PRIMARY KEY,
    event_id INTEGER NOT NULL REFERENCES events(id),
    user_id INTEGER NOT NULL REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS events_speed_dates (
    id SERIAL PRIMARY KEY,
    event_id INTEGER NOT NULL REFERENCES events(id),
    male_id INTEGER NOT NULL REFERENCES users(id),
    female_id INTEGER NOT NULL REFERENCES users(id),
    male_interested BOOLEAN,
    female_interested BOOLEAN,
    table_number INTEGER NOT NULL,
    round_number INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS event_timers (
    id SERIAL PRIMARY KEY,
    event_id INTEGER NOT NULL REFERENCES events(id),
    current_round INTEGER NOT NULL DEFAULT 1,
    final_round INTEGER NOT NULL DEFAULT 1,
    round_duration INTEGER NOT NULL DEFAULT 180,
    round_start_time TIMESTAMPTZ,
    is_paused BOOLEAN NOT NULL DEFAULT FALSE,
    pause_time_remaining INTEGER,
    break_duration INTEGER NOT NULL DEFAULT 90,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS event_waitlists (
    id SERIAL PRIMARY KEY,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    waitlisted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_event_user_waitlist UNIQUE (event_id, user_id)
);

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

CREATE TABLE IF NOT EXISTS email_jobs (
    id SERIAL PRIMARY KEY,
    job_type VARCHAR(64) NOT NULL,
    payload JSON NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    scheduled_for TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sent_at TIMESTAMPTZ,
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_email_jobs_status_scheduled_for
    ON email_jobs (status, scheduled_for);

-- Reconcile databases created by older application versions.
ALTER TABLE users ADD COLUMN IF NOT EXISTS reset_token VARCHAR(255);
ALTER TABLE users ADD COLUMN IF NOT EXISTS reset_token_expiration TIMESTAMPTZ;
ALTER TABLE events ADD COLUMN IF NOT EXISTS enforce_gender_balance BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE events ADD COLUMN IF NOT EXISTS num_rounds INTEGER;
ALTER TABLE events ADD COLUMN IF NOT EXISTS num_tables INTEGER;
ALTER TABLE events DROP COLUMN IF EXISTS event_timezone;
ALTER TABLE event_timers ADD COLUMN IF NOT EXISTS final_round INTEGER NOT NULL DEFAULT 1;
ALTER TABLE email_jobs DROP COLUMN IF EXISTS attempts;
