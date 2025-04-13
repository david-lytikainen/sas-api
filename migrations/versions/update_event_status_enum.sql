-- Drop the existing enum type (if it exists)
DROP TYPE IF EXISTS eventstatus CASCADE;

-- Create the new enum type
CREATE TYPE eventstatus AS ENUM ('DRAFT', 'SCHEDULED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED'); 