from datetime import datetime

from domains.maintenance.service import is_airworthy, log_flight_hours


def _overlaps(start_a, end_a, start_b, end_b):
    return start_a < end_b and start_b < end_a


def _is_valid_email(email):
    if not email or "@" not in email:
        return False
    local, _, domain = email.partition("@")
    return bool(local) and "." in domain


def create_student(conn, name, email):
    if not _is_valid_email(email):
        raise ValueError("invalid email")
    cur = conn.execute("INSERT INTO students (name, email) VALUES (?, ?)", (name, email))
    conn.commit()
    return cur.lastrowid


def create_instructor(conn, name, email, certificate_number):
    if not _is_valid_email(email):
        raise ValueError("invalid email")
    cur = conn.execute(
        "INSERT INTO instructors (name, email, certificate_number) VALUES (?, ?, ?)",
        (name, email, certificate_number),
    )
    conn.commit()
    return cur.lastrowid


def book_lesson(conn, student_id, instructor_id, aircraft_id, start_time, end_time):
    """
    Book a lesson if the instructor and aircraft are free and the aircraft
    is airworthy. Returns the new lesson id, or raises ValueError.
    """
    if end_time <= start_time:
        raise ValueError("end time must be after start time")

    airworthy, reason = is_airworthy(conn, aircraft_id)
    if not airworthy:
        raise ValueError(reason)

    existing = conn.execute(
        "SELECT instructor_id, aircraft_id, start_time, end_time FROM lessons "
        "WHERE status = 'scheduled' AND (instructor_id = ? OR aircraft_id = ?)",
        (instructor_id, aircraft_id),
    ).fetchall()

    for lesson in existing:
        if not _overlaps(start_time, end_time, lesson["start_time"], lesson["end_time"]):
            continue
        if lesson["instructor_id"] == instructor_id:
            raise ValueError("booking conflict: instructor is already booked in that window")
        if lesson["aircraft_id"] == aircraft_id:
            raise ValueError("booking conflict: aircraft is already booked in that window")

    cur = conn.execute(
        "INSERT INTO lessons (student_id, instructor_id, aircraft_id, start_time, end_time, status) "
        "VALUES (?, ?, ?, ?, ?, 'scheduled')",
        (student_id, instructor_id, aircraft_id, start_time, end_time),
    )
    conn.commit()
    return cur.lastrowid


def complete_lesson(conn, lesson_id):
    """
    Mark a scheduled lesson completed and log its duration as flight hours
    against the aircraft it used. Raises ValueError if the lesson doesn't
    exist or isn't currently scheduled.
    """
    lesson = conn.execute(
        "SELECT aircraft_id, start_time, end_time, status FROM lessons WHERE id = ?",
        (lesson_id,),
    ).fetchone()

    if lesson is None or lesson["status"] != "scheduled":
        raise ValueError("lesson is not scheduled")

    start = datetime.fromisoformat(lesson["start_time"])
    end = datetime.fromisoformat(lesson["end_time"])
    duration_hours = (end - start).total_seconds() / 3600

    conn.execute("UPDATE lessons SET status = 'completed' WHERE id = ?", (lesson_id,))
    conn.commit()
    log_flight_hours(conn, lesson["aircraft_id"], duration_hours)
