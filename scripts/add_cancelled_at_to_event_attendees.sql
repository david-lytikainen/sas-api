-- Add cancelled_at timestamp column to events_attendees table
-- This column will track when a registration was cancelled for analytics purposes

ALTER TABLE events_attendees 
ADD COLUMN IF NOT EXISTS cancelled_at TIMESTAMP WITH TIME ZONE NULL;

-- Add a comment to document the purpose of this column
COMMENT ON COLUMN events_attendees.cancelled_at IS 'Timestamp when the registration was cancelled. NULL if never cancelled.'; 