-- Local setup, run by the db-init service in docker-compose.yml.
-- Idempotent: safe to run on every `docker compose up`.
-- Creates one database per service and one login per service that can only
-- use its own database. Passwords come in as sqlcmd variables, not from this file.

IF DB_ID('maintenance') IS NULL CREATE DATABASE maintenance;
IF DB_ID('scheduling') IS NULL CREATE DATABASE scheduling;
GO

IF SUSER_ID('maintenance_user') IS NULL
    CREATE LOGIN maintenance_user
    WITH PASSWORD = '$(MAINTENANCE_DB_PASSWORD)', DEFAULT_DATABASE = maintenance;
IF SUSER_ID('scheduling_user') IS NULL
    CREATE LOGIN scheduling_user
    WITH PASSWORD = '$(SCHEDULING_DB_PASSWORD)', DEFAULT_DATABASE = scheduling;
GO

-- db_owner on its own database only, so the service can run its migrations.
USE maintenance;
IF USER_ID('maintenance_user') IS NULL CREATE USER maintenance_user FOR LOGIN maintenance_user;
ALTER ROLE db_owner ADD MEMBER maintenance_user;
GO

USE scheduling;
IF USER_ID('scheduling_user') IS NULL CREATE USER scheduling_user FOR LOGIN scheduling_user;
ALTER ROLE db_owner ADD MEMBER scheduling_user;
GO
