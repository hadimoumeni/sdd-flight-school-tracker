"""SQL for the scheduling database (students, instructors, lessons)."""

from sqlalchemy import text


def list_students(conn):
    return conn.execute(text("SELECT id, name, email FROM students ORDER BY name")).mappings().all()


def create_student(conn, name, email):
    return conn.execute(
        text("INSERT INTO students (name, email) OUTPUT INSERTED.id VALUES (:name, :email)"),
        {"name": name, "email": email},
    ).scalar_one()


def list_instructors(conn):
    return (
        conn.execute(
            text("SELECT id, name, email, certificate_number FROM instructors ORDER BY name")
        )
        .mappings()
        .all()
    )


def create_instructor(conn, name, email, certificate_number):
    return conn.execute(
        text(
            "INSERT INTO instructors (name, email, certificate_number) OUTPUT INSERTED.id "
            "VALUES (:name, :email, :certificate_number)"
        ),
        {"name": name, "email": email, "certificate_number": certificate_number},
    ).scalar_one()


def list_lessons(conn):
    return (
        conn.execute(
            text(
                "SELECT lessons.id, lessons.student_id, students.name AS student_name, "
                "lessons.instructor_id, instructors.name AS instructor_name, "
                "lessons.aircraft_id, lessons.start_time, lessons.end_time, lessons.status "
                "FROM lessons "
                "JOIN students ON students.id = lessons.student_id "
                "JOIN instructors ON instructors.id = lessons.instructor_id "
                "ORDER BY lessons.start_time"
            )
        )
        .mappings()
        .all()
    )


def get_lesson(conn, lesson_id):
    return (
        conn.execute(
            text(
                "SELECT id, aircraft_id, start_time, end_time, status FROM lessons WHERE id = :id"
            ),
            {"id": lesson_id},
        )
        .mappings()
        .first()
    )


def scheduled_lessons_for(conn, instructor_id, aircraft_id):
    return (
        conn.execute(
            text(
                "SELECT instructor_id, aircraft_id, start_time, end_time FROM lessons "
                "WHERE status = 'scheduled' "
                "AND (instructor_id = :instructor_id OR aircraft_id = :aircraft_id)"
            ),
            {"instructor_id": instructor_id, "aircraft_id": aircraft_id},
        )
        .mappings()
        .all()
    )


def student_exists(conn, student_id):
    row = conn.execute(text("SELECT 1 FROM students WHERE id = :id"), {"id": student_id})
    return row.first() is not None


def instructor_exists(conn, instructor_id):
    row = conn.execute(text("SELECT 1 FROM instructors WHERE id = :id"), {"id": instructor_id})
    return row.first() is not None


def create_lesson(conn, student_id, instructor_id, aircraft_id, start, end):
    return conn.execute(
        text(
            "INSERT INTO lessons (student_id, instructor_id, aircraft_id, start_time, end_time) "
            "OUTPUT INSERTED.id "
            "VALUES (:student_id, :instructor_id, :aircraft_id, :start, :end)"
        ),
        {
            "student_id": student_id,
            "instructor_id": instructor_id,
            "aircraft_id": aircraft_id,
            "start": start,
            "end": end,
        },
    ).scalar_one()


def mark_completed(conn, lesson_id):
    conn.execute(
        text("UPDATE lessons SET status = 'completed' WHERE id = :id"),
        {"id": lesson_id},
    )


def touch_health_check(conn):
    """Write one row; True if the database accepted the write."""
    result = conn.execute(
        text("UPDATE health_check SET checked_at = SYSUTCDATETIME() WHERE id = 1")
    )
    return result.rowcount == 1
