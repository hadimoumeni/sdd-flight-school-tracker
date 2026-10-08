from datetime import datetime, timezone

from flask import Blueprint, redirect, render_template, request, url_for

from db import get_connection
from domains.maintenance.service import is_airworthy

bp = Blueprint("maintenance", __name__, url_prefix="/maintenance")


@bp.route("/")
def index():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM aircraft ORDER BY tail_number").fetchall()
    aircraft = []
    for row in rows:
        airworthy, reason = is_airworthy(conn, row["id"])
        aircraft.append({**dict(row), "airworthy": airworthy, "reason": reason})

    squawks = conn.execute(
        "SELECT squawks.*, aircraft.tail_number FROM squawks "
        "JOIN aircraft ON aircraft.id = squawks.aircraft_id "
        "WHERE squawks.resolved_at IS NULL "
        "ORDER BY squawks.reported_at"
    ).fetchall()
    conn.close()

    return render_template("maintenance.html", aircraft=aircraft, squawks=squawks)


@bp.route("/aircraft", methods=["POST"])
def create_aircraft():
    conn = get_connection()
    conn.execute(
        "INSERT INTO aircraft (tail_number, model, total_hours, hours_at_last_inspection) "
        "VALUES (?, ?, 0, 0)",
        (request.form["tail_number"], request.form["model"]),
    )
    conn.commit()
    conn.close()
    return redirect(url_for("maintenance.index"))


@bp.route("/squawks", methods=["POST"])
def report_squawk():
    conn = get_connection()
    conn.execute(
        "INSERT INTO squawks (aircraft_id, description, severity, reported_at) "
        "VALUES (?, ?, ?, ?)",
        (
            request.form["aircraft_id"],
            request.form["description"],
            request.form["severity"],
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    conn.close()
    return redirect(url_for("maintenance.index"))


@bp.route("/squawks/<int:squawk_id>/resolve", methods=["POST"])
def resolve_squawk(squawk_id):
    conn = get_connection()
    conn.execute(
        "UPDATE squawks SET resolved_at = ? WHERE id = ?",
        (datetime.now(timezone.utc).isoformat(), squawk_id),
    )
    conn.commit()
    conn.close()
    return redirect(url_for("maintenance.index"))
