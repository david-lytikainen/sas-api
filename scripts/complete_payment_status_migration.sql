-- Complete migration for payment status feature
-- This script adds payment tracking to event attendees and updates the registration status enum

-- Step 1: Add new enum values to RegistrationStatus
ALTER TYPE registrationstatus ADD VALUE IF NOT EXISTS 'WAITLISTED';
ALTER TYPE registrationstatus ADD VALUE IF NOT EXISTS 'PENDING_PAYMENT';

-- Step 2: Add payment_status column
ALTER TABLE events_attendees 
ADD COLUMN IF NOT EXISTS payment_status VARCHAR(20) NOT NULL DEFAULT 'paid';

-- Step 3: Add payment_due_date column for pending payments
ALTER TABLE events_attendees 
ADD COLUMN IF NOT EXISTS payment_due_date TIMESTAMP WITH TIME ZONE NULL;

-- Step 4: Create indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_events_attendees_payment_status ON events_attendees(payment_status);
CREATE INDEX IF NOT EXISTS idx_events_attendees_payment_due_date ON events_attendees(payment_due_date);

-- Step 5: Update existing records to have 'paid' status (they were registered through normal flow)
UPDATE events_attendees SET payment_status = 'paid' WHERE payment_status = 'paid';

-- Step 6: Add check constraint for valid payment statuses
DO $$
BEGIN
    ALTER TABLE events_attendees 
    ADD CONSTRAINT chk_payment_status 
    CHECK (payment_status IN ('paid', 'pending', 'waived'));
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- Step 7: Add comments to explain the new columns
COMMENT ON COLUMN events_attendees.payment_status IS 'Payment status: paid (payment completed), pending (payment required), waived (free event or admin override)';
COMMENT ON COLUMN events_attendees.payment_due_date IS 'Date by which payment must be completed for pending payments';

-- Step 8: Display summary
SELECT 'Migration completed successfully. Payment status feature is now available.' as result; 