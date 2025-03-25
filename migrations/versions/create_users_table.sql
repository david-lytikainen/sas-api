-- Create the gender enum type if it doesn't exist
CREATE TYPE IF NOT EXISTS gender AS ENUM ('MALE', 'FEMALE', 'NOT_SPECIFIED');

-- Create the users table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    role_id INTEGER NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    first_name VARCHAR(255) NOT NULL,
    last_name VARCHAR(255) NOT NULL,
    phone VARCHAR(20) NOT NULL,
    gender gender NOT NULL,
    age INTEGER NOT NULL,
    church_id INTEGER,
    denomination_id INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
); 