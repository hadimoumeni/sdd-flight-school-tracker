# Flight School Ops

Scheduling and maintenance tracking for a small flight school: book lessons
against students, instructors and aircraft, and track which aircraft are
legal to fly (100-hour inspection cycle, pilot-reported squawks).

## Setup

### Directly on a machine

```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

### With Docker

```
docker build -t flight-school-ops .
docker run -p 8000:8000 -v flight-school-data:/data flight-school-ops
```

### Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `PORT` | `8000` | Port the app listens on. |
| `DATA_DIR` | `./data` locally, `/data` in the container | Directory holding the SQLite file (`flight_school.db`). |
| `SECRET_KEY` | `dev-secret-key` | Flask session/flash-message signing key. |

No seed data: every table (students, instructors, aircraft, lessons,
squawks) is populated through the app's own forms, not reference data that
needs loading on first boot — so there's nothing to ship as a `seed.sql`
and no first-boot loading logic to make idempotent.

### §7 container-run evidence

```
=== SDD Assignment 1 contract check ===
Repository: /Users/hadimoumeni/Downloads/sdd-flight-school-tracker

==> Repository shape
  PASS  one Dockerfile, one manifest (requirements.txt)

==> Build from a clean context, no build args
  PASS  image built
  PASS  image size 53 MB

==> Start on PORT=8000 and reach it from the host
  PASS  HTTP 302 from http://localhost:8000/

==> SQLite file under DATA_DIR
  PASS  found in /data: flight_school.db

==> Data persists, and a second boot does not re-seed
  PASS  volume at /data persists
  PASS  row counts unchanged across restart: aircraft=0 instructors=0 lessons=0 squawks=0 students=0

==> PORT override is honoured (not hardcoded)
  PASS  HTTP 302 from http://localhost:9123/

=== ALL CHECKS PASSED ===
```

## Tests

```
python -m pytest --cov=domains.maintenance.service --cov=domains.scheduling.service --cov-report=term-missing
```

20 tests, 100% coverage on the two domains' business logic
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
