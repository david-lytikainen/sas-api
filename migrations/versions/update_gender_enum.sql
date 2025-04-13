-- Drop the existing enum type (if it exists)
DROP TYPE IF EXISTS gender CASCADE;

-- Create the new enum type
CREATE TYPE gender AS ENUM ('MALE', 'FEMALE', 'NOT_SPECIFIED');

-- Update the users table to use the new enum type
ALTER TABLE users ALTER COLUMN gender TYPE gender USING gender::text::gender; 