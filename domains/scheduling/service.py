from domains.maintenance.service import is_airworthy


def _overlaps(start_a, end_a, start_b, end_b):
    return start_a < end_b and start_b < end_a


def book_lesson(conn, student_id, instructor_id, aircraft_id, start_time, end_time):
    """
    Book a lesson if the instructor and aircraft are free and the aircraft
    is airworthy. Returns the new lesson id, or raises ValueError.
    """
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
