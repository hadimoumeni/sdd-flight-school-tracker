# Flight School Ops

Scheduling and maintenance tracking for a small flight school: book lessons
against students, instructors and aircraft, and track which aircraft are
legal to fly (100-hour inspection cycle, pilot-reported squawks).

## Setup

```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Runs on port 5000 by default (set `PORT` to override). SQLite database is
created under `./data` (set `DATA_DIR` to override).

## Tests

```
python -m pytest --cov=domains.maintenance.service --cov=domains.scheduling.service --cov-report=term-missing
```

12 tests, 100% coverage on the two domains' business logic
(`domains/*/service.py`). Routes (`domains/*/routes.py`) are intentionally
excluded from the coverage target: they're Flask glue (read a form, call the
service, redirect), which is what the assignment's testing section says not
to chase coverage on. They were verified by hand by running the app and
exercising every route over real HTTP.

## Architecture

Two domains, each with its own SQLite tables and a `service.py` holding the
business logic:

- `domains/maintenance` — aircraft airworthiness (100-hour inspection rule,
  safety squawks).
- `domains/scheduling` — lesson booking, conflict detection.

Scheduling calls into maintenance only through `is_airworthy(conn,
aircraft_id)`; it never reads the maintenance tables directly. See
`ADR.md` entry 2.
