#!/bin/bash
# ─────────────────────────────────────────────────────────────
# PostgreSQL initialization script
#
# This runs automatically when the PostgreSQL container starts
# for the first time (mounted via docker-compose volumes).
#
# It creates any extensions or initial configuration needed.
# The actual table creation happens via SQLAlchemy at app startup.
# ─────────────────────────────────────────────────────────────

set -e

echo "Initializing FPV Deal Finder database..."

# Connect to the fpvdeals database and create extensions
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Enable UUID generation (useful for future use)
    CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

    -- Enable better text search
    CREATE EXTENSION IF NOT EXISTS "pg_trgm";

    -- Log the setup
    SELECT 'FPV Deal Finder database initialized successfully' as status;
EOSQL

echo "Database initialization complete!"
