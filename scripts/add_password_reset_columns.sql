-- This script adds columns to the 'users' table for password reset functionality.

-- Add the reset_token column to store the unique password reset token.
-- It is a string with a max length of 255 characters and must be unique.
ALTER TABLE users ADD COLUMN reset_token VARCHAR(255) UNIQUE;

-- Add the reset_token_expiration column to store the timestamp
-- when the reset token expires. It includes timezone information.
ALTER TABLE users ADD COLUMN reset_token_expiration TIMESTAMP WITH TIME ZONE; 