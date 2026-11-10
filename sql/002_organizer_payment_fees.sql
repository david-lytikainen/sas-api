ALTER TABLE event_payments
    ADD COLUMN IF NOT EXISTS application_fee_cents INTEGER,
    ADD COLUMN IF NOT EXISTS stripe_processing_fee_cents INTEGER;
