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

-- Only what the service needs on its own database: create and change tables (migrations),
-- read and write rows. Same roles as the contained users on Azure (see infra/setup.sh).
USE maintenance;
IF USER_ID('maintenance_user') IS NULL CREATE USER maintenance_user FOR LOGIN maintenance_user;
ALTER ROLE db_ddladmin ADD MEMBER maintenance_user;
ALTER ROLE db_datareader ADD MEMBER maintenance_user;
ALTER ROLE db_datawriter ADD MEMBER maintenance_user;
GO

USE scheduling;
IF USER_ID('scheduling_user') IS NULL CREATE USER scheduling_user FOR LOGIN scheduling_user;
ALTER ROLE db_ddladmin ADD MEMBER scheduling_user;
ALTER ROLE db_datareader ADD MEMBER scheduling_user;
ALTER ROLE db_datawriter ADD MEMBER scheduling_user;
GO
