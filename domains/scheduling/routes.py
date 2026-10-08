from flask import Blueprint, flash, redirect, render_template, request, url_for

from db import get_connection
from domains.scheduling.service import book_lesson

bp = Blueprint("scheduling", __name__, url_prefix="/scheduling")


@bp.route("/")
def index():
    conn = get_connection()
    lessons = conn.execute(
        "SELECT lessons.*, students.name AS student_name, "
        "instructors.name AS instructor_name, aircraft.tail_number "
        "FROM lessons "
        "JOIN students ON students.id = lessons.student_id "
        "JOIN instructors ON instructors.id = lessons.instructor_id "
        "JOIN aircraft ON aircraft.id = lessons.aircraft_id "
        "ORDER BY lessons.start_time"
    ).fetchall()
    students = conn.execute("SELECT * FROM students ORDER BY name").fetchall()
    instructors = conn.execute("SELECT * FROM instructors ORDER BY name").fetchall()
    aircraft = conn.execute("SELECT * FROM aircraft ORDER BY tail_number").fetchall()
    conn.close()

    return render_template(
        "scheduling.html",
        lessons=lessons,
        students=students,
        instructors=instructors,
        aircraft=aircraft,
    )


@bp.route("/students", methods=["POST"])
def create_student():
    conn = get_connection()
    conn.execute(
        "INSERT INTO students (name, email) VALUES (?, ?)",
        (request.form["name"], request.form["email"]),
    )
    conn.commit()
    conn.close()
    return redirect(url_for("scheduling.index"))


@bp.route("/instructors", methods=["POST"])
def create_instructor():
    conn = get_connection()
    conn.execute(
        "INSERT INTO instructors (name, email, certificate_number) VALUES (?, ?, ?)",
        (request.form["name"], request.form["email"], request.form["certificate_number"]),
    )
    conn.commit()
    conn.close()
    return redirect(url_for("scheduling.index"))


@bp.route("/lessons", methods=["POST"])
def create_lesson():
    conn = get_connection()
    try:
        book_lesson(
            conn,
            request.form["student_id"],
            request.form["instructor_id"],
            request.form["aircraft_id"],
            request.form["start_time"],
            request.form["end_time"],
        )
    except ValueError as exc:
        flash(str(exc))
    conn.close()
    return redirect(url_for("scheduling.index"))
