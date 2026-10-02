from domains.maintenance.service import is_airworthy, log_flight_hours


def test_fresh_aircraft_is_airworthy(conn, aircraft_id):
    airworthy, reason = is_airworthy(conn, aircraft_id)
    assert airworthy is True
    assert reason is None


def test_aircraft_over_100_hours_since_inspection_is_grounded(conn, aircraft_id):
    conn.execute(
        "UPDATE aircraft SET total_hours = 110, hours_at_last_inspection = 0 WHERE id = ?",
        (aircraft_id,),
    )
    conn.commit()

    airworthy, reason = is_airworthy(conn, aircraft_id)
    assert airworthy is False
    assert "100-hour inspection" in reason


def test_aircraft_under_100_hours_since_inspection_is_airworthy(conn, aircraft_id):
    conn.execute(
        "UPDATE aircraft SET total_hours = 95, hours_at_last_inspection = 10 WHERE id = ?",
        (aircraft_id,),
    )
    conn.commit()

    airworthy, reason = is_airworthy(conn, aircraft_id)
    assert airworthy is True


def test_aircraft_with_open_safety_squawk_is_grounded(conn, aircraft_id):
    conn.execute(
        "INSERT INTO squawks (aircraft_id, description, severity, reported_at) "
        "VALUES (?, ?, 'safety', '2026-10-01')",
        (aircraft_id, "Left brake not holding"),
    )
    conn.commit()

    airworthy, reason = is_airworthy(conn, aircraft_id)
    assert airworthy is False
    assert "Left brake not holding" in reason


def test_aircraft_with_resolved_safety_squawk_is_airworthy(conn, aircraft_id):
    conn.execute(
        "INSERT INTO squawks (aircraft_id, description, severity, reported_at, resolved_at) "
        "VALUES (?, ?, 'safety', '2026-10-01', '2026-10-02')",
        (aircraft_id, "Left brake not holding"),
    )
    conn.commit()

    airworthy, reason = is_airworthy(conn, aircraft_id)
    assert airworthy is True


def test_aircraft_with_open_minor_squawk_is_airworthy(conn, aircraft_id):
    conn.execute(
        "INSERT INTO squawks (aircraft_id, description, severity, reported_at) "
        "VALUES (?, ?, 'minor', '2026-10-01')",
        (aircraft_id, "Cosmetic paint chip"),
    )
    conn.commit()

    airworthy, reason = is_airworthy(conn, aircraft_id)
    assert airworthy is True


def test_log_flight_hours_increments_total_hours(conn, aircraft_id):
    log_flight_hours(conn, aircraft_id, 2.5)

    total = conn.execute(
        "SELECT total_hours FROM aircraft WHERE id = ?", (aircraft_id,)
    ).fetchone()["total_hours"]
    assert total == 2.5
