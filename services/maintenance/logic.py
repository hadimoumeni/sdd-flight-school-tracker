"""Maintenance business rules. Pure functions: no database, no HTTP."""

HOURS_BETWEEN_INSPECTIONS = 100
SEVERITIES = ("minor", "safety")


def airworthiness(total_hours, hours_at_last_inspection, open_safety_squawks):
    """
    Decide whether an aircraft may be flown.

    open_safety_squawks is the list of descriptions of unresolved safety squawks.
    Returns (True, None) if airworthy, or (False, reason) if grounded.
    """
    if total_hours - hours_at_last_inspection >= HOURS_BETWEEN_INSPECTIONS:
        return False, "grounded: 100-hour inspection overdue"
    if open_safety_squawks:
        return False, f"grounded: open safety squawk - {open_safety_squawks[0]}"
    return True, None


def validate_aircraft(tail_number, model):
    if not tail_number or not model:
        raise ValueError("tail number and model are required")


def validate_squawk(description, severity):
    if not description:
        raise ValueError("description is required")
    if severity not in SEVERITIES:
        raise ValueError("severity must be 'minor' or 'safety'")


def validate_hours(hours):
    if not isinstance(hours, (int, float)) or hours <= 0:
        raise ValueError("hours must be a positive number")
