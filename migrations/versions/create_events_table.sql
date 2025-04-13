-- Drop and recreate the eventstatus enum
DROP TYPE IF EXISTS eventstatus CASCADE;
CREATE TYPE eventstatus AS ENUM ('DRAFT', 'SCHEDULED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED');

-- Drop and recreate the events table
DROP TABLE IF EXISTS events CASCADE;
CREATE TABLE events (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    creator_id INTEGER NOT NULL REFERENCES users(id),
    starts_at TIMESTAMP WITH TIME ZONE NOT NULL,
    ends_at TIMESTAMP WITH TIME ZONE NOT NULL,
    address VARCHAR(255) NOT NULL,
    max_capacity INTEGER NOT NULL,
    status eventstatus NOT NULL,
    price_per_person DECIMAL(10,2) NOT NULL,
    registration_deadline TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
); 