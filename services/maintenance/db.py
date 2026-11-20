"""Database connection and versioned migrations for SQL Server.

Run as a script (`python db.py`) on container start: it waits for the
database, then applies any migrations that have not been applied yet.
"""

import logging
import os
import re
import time
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
# A line containing only GO ends a batch, as in sqlcmd. SQL Server compiles a whole batch
# before running it, so a column added with ALTER TABLE can only be used in a later batch.
BATCH_SEPARATOR = re.compile(r"^\s*GO\s*$", re.MULTILINE | re.IGNORECASE)

log = logging.getLogger(__name__)
_engine = None


def get_engine():
    """One engine per process, created on first use from DATABASE_URL."""
    global _engine
    if _engine is None:
        _engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
    return _engine


def wait_for_database(engine, attempts=10, delay=2):
    """Retry with backoff: a paused Azure SQL database takes up to a minute to resume."""
    for attempt in range(1, attempts + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return
        except DBAPIError as exc:
            if attempt == attempts:
                raise
            log.warning("database not ready (attempt %d/%d): %s", attempt, attempts, exc)
            time.sleep(delay)
            delay = min(delay * 2, 30)


def run_migrations(engine):
    """Apply each migrations/*.sql file once, in name order, recording it in schema_migrations."""
    with engine.begin() as conn:
        conn.execute(
            text(
                "IF OBJECT_ID('schema_migrations') IS NULL "
                "CREATE TABLE schema_migrations ("
                "  version NVARCHAR(100) PRIMARY KEY,"
                "  applied_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME())"
            )
        )
        applied = set(conn.execute(text("SELECT version FROM schema_migrations")).scalars())

    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        if path.name in applied:
            continue
        # One transaction per migration: the file and its record succeed or fail together.
        with engine.begin() as conn:
            for batch in BATCH_SEPARATOR.split(path.read_text()):
                if batch.strip():
                    conn.exec_driver_sql(batch)
            conn.execute(
                text("INSERT INTO schema_migrations (version) VALUES (:version)"),
                {"version": path.name},
            )
        log.info("applied migration %s", path.name)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    engine = get_engine()
    wait_for_database(engine)
    run_migrations(engine)
