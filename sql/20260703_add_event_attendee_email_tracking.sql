ALTER TABLE events_attendees
ADD COLUMN IF NOT EXISTS registration_confirmation_sent_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS reminder_one_month_sent_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS reminder_one_week_sent_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS reminder_one_day_sent_at TIMESTAMPTZ;
