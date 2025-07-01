-- Migration to add payment_status field to event_attendees table
-- This allows tracking whether attendees have paid or are pending payment

-- Add payment_status column
ALTER TABLE events_attendees 
ADD COLUMN payment_status VARCHAR(20) NOT NULL DEFAULT 'paid';

-- Add payment_due_date column for pending payments
ALTER TABLE events_attendees 
ADD COLUMN payment_due_date TIMESTAMP WITH TIME ZONE NULL;

-- Create index for efficient querying of pending payments
CREATE INDEX idx_events_attendees_payment_status ON events_attendees(payment_status);
CREATE INDEX idx_events_attendees_payment_due_date ON events_attendees(payment_due_date);

-- Update existing records to have 'paid' status (since they were registered through normal flow)
UPDATE events_attendees SET payment_status = 'paid' WHERE payment_status = 'paid';

-- Add check constraint for valid payment statuses
ALTER TABLE events_attendees 
ADD CONSTRAINT chk_payment_status 
CHECK (payment_status IN ('paid', 'pending', 'waived'));

-- Add comment to explain the new columns
COMMENT ON COLUMN events_attendees.payment_status IS 'Payment status: paid (payment completed), pending (payment required), waived (free event or admin override)';
COMMENT ON COLUMN events_attendees.payment_due_date IS 'Date by which payment must be completed for pending payments'; 