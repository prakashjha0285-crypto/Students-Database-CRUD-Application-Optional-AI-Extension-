"""SQLite connection handling and schema creation (standard library only)."""
import os
import sqlite3
from typing import Iterator

DEFAULT_DB_PATH = "students.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS students (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    name             TEXT NOT NULL,
    date_of_birth    TEXT NOT NULL,              -- ISO format: YYYY-MM-DD
    email            TEXT UNIQUE,
    phone            TEXT,
    course           TEXT,
    address          TEXT,
    enrollment_date  TEXT,                       -- ISO format: YYYY-MM-DD
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL,
    CHECK (email IS NOT NULL OR phone IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS idx_students_name ON students (name);
CREATE INDEX IF NOT EXISTS idx_students_course ON students (course);
CREATE INDEX IF NOT EXISTS idx_students_dob ON students (date_of_birth);
"""


def get_db_path() -> str:
    """Read the DB path at call time so tests/users can override it via env var."""
    return os.getenv("STUDENTS_DB_PATH", DEFAULT_DB_PATH)


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create the table (and indexes) if they do not exist yet."""
    conn = connect()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def get_db() -> Iterator[sqlite3.Connection]:
    """FastAPI dependency: one short-lived connection per request."""
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()
