import os
import sqlite3


def get_db_path():
    data_dir = os.environ.get("DATA_DIR", "./data")
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "flight_school.db")


def get_connection():
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS instructors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            certificate_number TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS aircraft (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tail_number TEXT NOT NULL UNIQUE,
            model TEXT NOT NULL,
            total_hours REAL NOT NULL DEFAULT 0,
            hours_at_last_inspection REAL NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS squawks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            aircraft_id INTEGER NOT NULL REFERENCES aircraft(id),
            description TEXT NOT NULL,
            severity TEXT NOT NULL CHECK (severity IN ('minor', 'safety')),
            reported_at TEXT NOT NULL,
            resolved_at TEXT
        );

        CREATE TABLE IF NOT EXISTS lessons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL REFERENCES students(id),
            instructor_id INTEGER NOT NULL REFERENCES instructors(id),
            aircraft_id INTEGER NOT NULL REFERENCES aircraft(id),
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'scheduled'
        );
    """)
    conn.commit()
    conn.close()
