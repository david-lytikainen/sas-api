-- Create the event_waitlists table if it doesn't already exist
-- This table stores entries for users waitlisted for specific events.

CREATE TABLE IF NOT EXISTS event_waitlists (
    id SERIAL PRIMARY KEY,
    event_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    waitlisted_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_event
        FOREIGN KEY(event_id)
        REFERENCES events(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_user
        FOREIGN KEY(user_id)
        REFERENCES users(id)
        ON DELETE CASCADE,

    CONSTRAINT uq_event_user_waitlist UNIQUE (event_id, user_id)
);