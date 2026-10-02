HOURS_BETWEEN_INSPECTIONS = 100


def is_airworthy(conn, aircraft_id):
    """
    Decide whether an aircraft may be flown.

    Returns (True, None) if airworthy, or (False, reason) if grounded.
    """
    aircraft = conn.execute(
        "SELECT total_hours, hours_at_last_inspection FROM aircraft WHERE id = ?",
        (aircraft_id,),
    ).fetchone()

    hours_since_inspection = aircraft["total_hours"] - aircraft["hours_at_last_inspection"]
    if hours_since_inspection >= HOURS_BETWEEN_INSPECTIONS:
        return False, "grounded: 100-hour inspection overdue"

    squawk = conn.execute(
        "SELECT description FROM squawks "
        "WHERE aircraft_id = ? AND severity = 'safety' AND resolved_at IS NULL",
        (aircraft_id,),
    ).fetchone()
    if squawk is not None:
        return False, f"grounded: open safety squawk - {squawk['description']}"

    return True, None


def log_flight_hours(conn, aircraft_id, hours):
    """Add flown hours to an aircraft's running total."""
    conn.execute(
        "UPDATE aircraft SET total_hours = total_hours + ? WHERE id = ?",
        (hours, aircraft_id),
    )
    conn.commit()
