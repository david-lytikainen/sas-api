CREATE TABLE IF NOT EXISTS walkin_attendees (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    CONSTRAINT uq_walkin_attendee_user_event UNIQUE (user_id, event_id)
);
