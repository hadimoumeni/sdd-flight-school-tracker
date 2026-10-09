import pytest

from domains.scheduling.service import book_lesson


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
