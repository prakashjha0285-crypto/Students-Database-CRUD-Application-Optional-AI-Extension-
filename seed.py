"""Load DUMMY sample students (safe to publish; no real personal data).

Usage:  python seed.py
"""
from app import crud
from app.database import connect, init_db

SAMPLE_STUDENTS = [
    ("Aarav Sharma", "2004-03-15", "aarav.sharma@example.com", "+91 90000 00001", "Python Backend Development", "2024-07-01"),
    ("Diya Patel", "2005-11-02", "diya.patel@example.com", "+91 90000 00002", "Python Backend Development", "2024-07-01"),
    ("Rohan Das", "2003-06-21", "rohan.das@example.com", "+91 90000 00003", "Data Science", "2023-08-10"),
    ("Ananya Iyer", "2006-01-09", "ananya.iyer@example.com", "+91 90000 00004", "Web Development", "2024-09-15"),
    ("Kabir Singh", "2005-04-30", "kabir.singh@example.com", "+91 90000 00005", "Data Science", "2024-01-20"),
    ("Meera Nair", "2007-08-12", "meera.nair@example.com", None, "Web Development", "2025-02-03"),
    ("Vihaan Gupta", "2002-12-25", "vihaan.gupta@example.com", "+91 90000 00007", "Cloud Computing", "2022-07-18"),
    ("Isha Reddy", "2006-05-17", None, "+91 90000 00008", "Python Backend Development", "2025-01-12"),
    ("Arjun Mehta", "2004-09-08", "arjun.mehta@example.com", "+91 90000 00009", "Cloud Computing", "2023-03-05"),
    ("Sara Khan", "2005-02-14", "sara.khan@example.com", "+91 90000 00010", "Data Science", "2024-06-24"),
]


def main() -> None:
    init_db()
    conn = connect()
    added = skipped = 0
    try:
        for name, dob, email, phone, course, enrolled in SAMPLE_STUDENTS:
            # Skip if already seeded (email is unique, but phone-only rows need this check).
            if any(
                s["name"] == name and s["date_of_birth"] == dob
                for s in crud.list_students(conn, limit=100, name=name)
            ):
                skipped += 1
                continue
            try:
                crud.create_student(
                    conn,
                    {
                        "name": name,
                        "date_of_birth": dob,
                        "email": email,
                        "phone": phone,
                        "course": course,
                        "enrollment_date": enrolled,
                    },
                )
                added += 1
            except crud.DuplicateEmailError:
                skipped += 1
    finally:
        conn.close()
    print(f"Seed complete: {added} added, {skipped} already present.")


if __name__ == "__main__":
    main()
