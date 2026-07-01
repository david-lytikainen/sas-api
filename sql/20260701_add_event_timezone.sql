ALTER TABLE events
ADD COLUMN IF NOT EXISTS event_timezone VARCHAR(64);

UPDATE events
SET event_timezone = 'UTC'
WHERE event_timezone IS NULL OR event_timezone = '';

ALTER TABLE events
ALTER COLUMN event_timezone SET NOT NULL;

ALTER TABLE events
ALTER COLUMN event_timezone SET DEFAULT 'UTC';
