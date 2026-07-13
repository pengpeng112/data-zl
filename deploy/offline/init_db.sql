-- Run once as the PostgreSQL DBA before applying Alembic migrations.
CREATE SCHEMA IF NOT EXISTS asset AUTHORIZATION asset_app;
GRANT USAGE, CREATE ON SCHEMA asset TO asset_app;
