-- FinAI PostgreSQL initialization
-- This runs automatically when the Docker container first starts

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- for text search

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE finai_db TO finai;
