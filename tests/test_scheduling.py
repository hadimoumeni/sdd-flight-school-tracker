import pytest

from domains.scheduling.service import (
    book_lesson,
    complete_lesson,
    create_instructor,
    create_student,
)


def test_book_lesson_succeeds_for_available_slot(conn, student_id, instructor_id, aircraft_id):
    lesson_id = book_lesson(
        conn, student_id, instructor_id, aircraft_id, "2026-10-05 09:00", "2026-10-05 10:00"
    )

    lesson = conn.execute("SELECT * FROM lessons WHERE id = ?", (lesson_id,)).fetchone()
    assert lesson["student_id"] == student_id
    assert lesson["instructor_id"] == instructor_id
    assert lesson["aircraft_id"] == aircraft_id
    assert lesson["status"] == "scheduled"


def test_double_booking_the_same_instructor_is_rejected(
    conn, student_id, instructor_id, aircraft_id
):
    book_lesson(
        conn, student_id, instructor_id, aircraft_id, "2026-10-05 09:00", "2026-10-05 10:00"
    )

    with pytest.raises(ValueError, match="instructor is already booked"):
        book_lesson(
            conn, student_id, instructor_id, aircraft_id, "2026-10-05 09:30", "2026-10-05 10:30"
        )


def test_double_booking_the_same_aircraft_is_rejected(
    conn, student_id, instructor_id, aircraft_id
):
    other_instructor = conn.execute(
        "INSERT INTO instructors (name, email, certificate_number) VALUES (?, ?, ?)",
        ("Sam Park", "sam@example.com", "CFI-9001"),
    ).lastrowid
    conn.commit()

    book_lesson(
        conn, student_id, instructor_id, aircraft_id, "2026-10-05 09:00", "2026-10-05 10:00"
    )

    with pytest.raises(ValueError, match="aircraft is already booked"):
        book_lesson(
            conn, student_id, other_instructor, aircraft_id, "2026-10-05 09:30", "2026-10-05 10:30"
        )


def test_non_overlapping_bookings_for_same_instructor_are_allowed(
    conn, student_id, instructor_id, aircraft_id
):
    book_lesson(
        conn, student_id, instructor_id, aircraft_id, "2026-10-05 09:00", "2026-10-05 10:00"
    )

    lesson_id = book_lesson(
        conn, student_id, instructor_id, aircraft_id, "2026-10-05 10:00", "2026-10-05 11:00"
    )

    assert lesson_id is not None


def test_booking_a_grounded_aircraft_is_rejected(conn, student_id, instructor_id, aircraft_id):
    conn.execute(
        "UPDATE aircraft SET total_hours = 110, hours_at_last_inspection = 0 WHERE id = ?",
        (aircraft_id,),
    )
    conn.commit()

    with pytest.raises(ValueError, match="100-hour inspection"):
        book_lesson(
            conn, student_id, instructor_id, aircraft_id, "2026-10-05 09:00", "2026-10-05 10:00"
        )


def test_booking_with_end_time_before_start_time_is_rejected(
    conn, student_id, instructor_id, aircraft_id
):
    with pytest.raises(ValueError, match="end time must be after start time"):
        book_lesson(
            conn, student_id, instructor_id, aircraft_id, "2026-10-05 10:00", "2026-10-05 09:00"
        )


def test_create_student_with_valid_email_succeeds(conn):
    student_id = create_student(conn, "Alex Rivera", "alex@example.com")

    row = conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
    assert row["name"] == "Alex Rivera"
    assert row["email"] == "alex@example.com"


def test_create_student_with_invalid_email_is_rejected(conn):
    with pytest.raises(ValueError, match="invalid email"):
        create_student(conn, "Alex Rivera", "not-an-email")


def test_create_instructor_with_invalid_email_is_rejected(conn):
    with pytest.raises(ValueError, match="invalid email"):
        create_instructor(conn, "Jordan Lee", "not-an-email", "CFI-4821")


def test_create_instructor_with_valid_email_succeeds(conn):
    instructor_id = create_instructor(conn, "Jordan Lee", "jordan@example.com", "CFI-4821")

    row = conn.execute(
        "SELECT * FROM instructors WHERE id = ?", (instructor_id,)
    ).fetchone()
    assert row["name"] == "Jordan Lee"
    assert row["certificate_number"] == "CFI-4821"


def test_completing_a_lesson_logs_flight_hours_and_marks_it_completed(
    conn, student_id, instructor_id, aircraft_id
):
    lesson_id = book_lesson(
        conn, student_id, instructor_id, aircraft_id, "2026-10-05 09:00", "2026-10-05 11:00"
    )

    complete_lesson(conn, lesson_id)

    lesson = conn.execute("SELECT * FROM lessons WHERE id = ?", (lesson_id,)).fetchone()
    assert lesson["status"] == "completed"

    aircraft = conn.execute(
        "SELECT total_hours FROM aircraft WHERE id = ?", (aircraft_id,)
    ).fetchone()
    assert aircraft["total_hours"] == 2.0


def test_completing_an_already_completed_lesson_is_rejected(
    conn, student_id, instructor_id, aircraft_id
):
    lesson_id = book_lesson(
        conn, student_id, instructor_id, aircraft_id, "2026-10-05 09:00", "2026-10-05 10:00"
    )
    complete_lesson(conn, lesson_id)

    with pytest.raises(ValueError, match="not scheduled"):
        complete_lesson(conn, lesson_id)


def test_completing_a_nonexistent_lesson_is_rejected(conn):
    with pytest.raises(ValueError, match="not scheduled"):
        complete_lesson(conn, 9999)
