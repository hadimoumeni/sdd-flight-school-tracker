import sqlite3

import pytest

from db import init_schema


@pytest.fixture
def conn():
    """An in-memory database with the real schema, closed after each test."""
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    init_schema(connection)
    yield connection
    connection.close()


@pytest.fixture
def aircraft_id(conn):
    """A fresh airworthy aircraft: 0 hours, nothing to flag."""
    cur = conn.execute(
        "INSERT INTO aircraft (tail_number, model, total_hours, hours_at_last_inspection) "
        "VALUES (?, ?, ?, ?)",
        ("N12345", "Cessna 172", 0, 0),
    )
    conn.commit()
    return cur.lastrowid


@pytest.fixture
def student_id(conn):
    cur = conn.execute(
        "INSERT INTO students (name, email) VALUES (?, ?)",
        ("Alex Rivera", "alex@example.com"),
    )
    conn.commit()
    return cur.lastrowid


@pytest.fixture
def instructor_id(conn):
    cur = conn.execute(
        "INSERT INTO instructors (name, email, certificate_number) VALUES (?, ?, ?)",
        ("Jordan Lee", "jordan@example.com", "CFI-4821"),
    )
    conn.commit()
    return cur.lastrowid
