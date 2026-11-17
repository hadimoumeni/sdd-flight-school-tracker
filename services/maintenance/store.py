"""SQL for the maintenance database (aircraft and squawks)."""

from sqlalchemy import text


def list_aircraft(conn):
    return (
        conn.execute(
            text(
                "SELECT id, tail_number, model, total_hours, hours_at_last_inspection "
                "FROM aircraft ORDER BY tail_number"
            )
        )
        .mappings()
        .all()
    )


def get_aircraft(conn, aircraft_id):
    return (
        conn.execute(
            text(
                "SELECT id, tail_number, model, total_hours, hours_at_last_inspection "
                "FROM aircraft WHERE id = :id"
            ),
            {"id": aircraft_id},
        )
        .mappings()
        .first()
    )


def create_aircraft(conn, tail_number, model):
    return conn.execute(
        text(
            "INSERT INTO aircraft (tail_number, model) OUTPUT INSERTED.id "
            "VALUES (:tail_number, :model)"
        ),
        {"tail_number": tail_number, "model": model},
    ).scalar_one()


def add_flight_hours(conn, aircraft_id, hours):
    """Returns False if the aircraft does not exist."""
    result = conn.execute(
        text("UPDATE aircraft SET total_hours = total_hours + :hours WHERE id = :id"),
        {"hours": hours, "id": aircraft_id},
    )
    return result.rowcount == 1


def open_safety_squawks(conn, aircraft_id):
    return list(
        conn.execute(
            text(
                "SELECT description FROM squawks "
                "WHERE aircraft_id = :id AND severity = 'safety' AND resolved_at IS NULL "
                "ORDER BY reported_at"
            ),
            {"id": aircraft_id},
        ).scalars()
    )


def list_open_squawks(conn):
    return (
        conn.execute(
            text(
                "SELECT squawks.id, squawks.aircraft_id, aircraft.tail_number, "
                "squawks.description, squawks.severity, squawks.reported_at "
                "FROM squawks JOIN aircraft ON aircraft.id = squawks.aircraft_id "
                "WHERE squawks.resolved_at IS NULL ORDER BY squawks.reported_at"
            )
        )
        .mappings()
        .all()
    )


def create_squawk(conn, aircraft_id, description, severity):
    return conn.execute(
        text(
            "INSERT INTO squawks (aircraft_id, description, severity) OUTPUT INSERTED.id "
            "VALUES (:aircraft_id, :description, :severity)"
        ),
        {"aircraft_id": aircraft_id, "description": description, "severity": severity},
    ).scalar_one()


def resolve_squawk(conn, squawk_id):
    """Returns False if there is no open squawk with that id."""
    result = conn.execute(
        text(
            "UPDATE squawks SET resolved_at = SYSUTCDATETIME() "
            "WHERE id = :id AND resolved_at IS NULL"
        ),
        {"id": squawk_id},
    )
    return result.rowcount == 1


def touch_health_check(conn):
    """Write one row; True if the database accepted the write."""
    result = conn.execute(
        text("UPDATE health_check SET checked_at = SYSUTCDATETIME() WHERE id = 1")
    )
    return result.rowcount == 1
