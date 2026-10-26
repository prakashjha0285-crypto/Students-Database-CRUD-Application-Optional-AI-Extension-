"""Data-access layer. Every query is parameterized (no string-built SQL values)."""
import sqlite3
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

FIELDS = (
    "name",
    "date_of_birth",
    "email",
    "phone",
    "course",
    "address",
    "enrollment_date",
)


class DuplicateEmailError(Exception):
    """Raised when an email address is already used by another student."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _like(value: str) -> str:
    """Build a safe 'contains' pattern (escapes LIKE wildcards)."""
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    return value.isoformat() if isinstance(value, date) else str(value)


def _build_where(
    name: Optional[str] = None,
    course: Optional[str] = None,
    email: Optional[str] = None,
    born_after: Optional[date] = None,
    born_before: Optional[date] = None,
):
    clauses: List[str] = []
    params: List[Any] = []
    if name:
        clauses.append("name LIKE ? ESCAPE '\\'")
        params.append(_like(name))
    if course:
        clauses.append("course LIKE ? ESCAPE '\\'")
        params.append(_like(course))
    if email:
        clauses.append("email = ?")
        params.append(email.strip().lower())
    if born_after:
        clauses.append("date_of_birth > ?")  # strictly after
        params.append(_iso(born_after))
    if born_before:
        clauses.append("date_of_birth < ?")  # strictly before
        params.append(_iso(born_before))
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


def _to_dict(row: Optional[sqlite3.Row]) -> Optional[Dict[str, Any]]:
    return dict(row) if row is not None else None


def get_student(conn: sqlite3.Connection, student_id: int) -> Optional[Dict[str, Any]]:
    row = conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
    return _to_dict(row)


def list_students(
    conn: sqlite3.Connection, limit: int = 20, offset: int = 0, **filters: Any
) -> List[Dict[str, Any]]:
    where, params = _build_where(**filters)
    rows = conn.execute(
        f"SELECT * FROM students{where} ORDER BY id LIMIT ? OFFSET ?",
        (*params, limit, offset),
    ).fetchall()
    return [dict(r) for r in rows]


def count_students(conn: sqlite3.Connection, **filters: Any) -> int:
    where, params = _build_where(**filters)
    return conn.execute(f"SELECT COUNT(*) FROM students{where}", params).fetchone()[0]


def distinct_courses(conn: sqlite3.Connection) -> List[str]:
    rows = conn.execute(
        "SELECT DISTINCT course FROM students WHERE course IS NOT NULL ORDER BY course"
    ).fetchall()
    return [r[0] for r in rows]


def all_names(conn: sqlite3.Connection) -> List[str]:
    return [r[0] for r in conn.execute("SELECT name FROM students ORDER BY id")]


def create_student(conn: sqlite3.Connection, data: Dict[str, Any]) -> Dict[str, Any]:
    now = _now()
    try:
        cur = conn.execute(
            """INSERT INTO students
               (name, date_of_birth, email, phone, course, address,
                enrollment_date, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (*[_iso(data.get(f)) for f in FIELDS], now, now),
        )
        conn.commit()
    except sqlite3.IntegrityError as exc:
        conn.rollback()
        if "students.email" in str(exc):
            raise DuplicateEmailError(data.get("email")) from exc
        raise
    return get_student(conn, cur.lastrowid)  # type: ignore[arg-type]


def replace_student(
    conn: sqlite3.Connection, student_id: int, data: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Overwrite every editable field of an existing student."""
    try:
        cur = conn.execute(
            """UPDATE students SET
                   name = ?, date_of_birth = ?, email = ?, phone = ?,
                   course = ?, address = ?, enrollment_date = ?, updated_at = ?
               WHERE id = ?""",
            (*[_iso(data.get(f)) for f in FIELDS], _now(), student_id),
        )
        conn.commit()
    except sqlite3.IntegrityError as exc:
        conn.rollback()
        if "students.email" in str(exc):
            raise DuplicateEmailError(data.get("email")) from exc
        raise
    if cur.rowcount == 0:
        return None
    return get_student(conn, student_id)


def delete_student(conn: sqlite3.Connection, student_id: int) -> bool:
    cur = conn.execute("DELETE FROM students WHERE id = ?", (student_id,))
    conn.commit()
    return cur.rowcount > 0
