# Flight School Ops

Scheduling and maintenance tracking for a small flight school: book lessons
against students, instructors and aircraft, and track which aircraft are
legal to fly (100-hour inspection cycle, pilot-reported squawks).

## Architecture

Two services, split along the seam from `ADR.md` entry 2. Each runs in its
own container and owns its own SQL Server database.

| Service | Folder | Owns | Local URL |
|---|---|---|---|
| maintenance | `services/maintenance` | `aircraft`, `squawks` | http://localhost:8001 |
| scheduling | `services/scheduling` | `students`, `instructors`, `lessons` | http://localhost:8002 |

Scheduling calls maintenance over HTTP (2 s timeout) when a lesson is booked
(`GET /aircraft/{id}/airworthiness`) and when a lesson is completed
(`POST /aircraft/{id}/flight-hours`). If maintenance is down, scheduling keeps
serving its own data and those two actions return `503` with a clear message.

The UI (`ui/`) is static HTML and JavaScript. The browser calls both services
directly; their base URLs come from `ui/config.js` (local values in the repo,
overwritten with the Azure URLs at deploy time). Locally, compose serves `ui/`
with a stock `nginx:alpine` image. If a service is down or still starting, the
page shows "starting up or unavailable" with a Retry button, and every call
gives up after 15 s instead of hanging.

Each service is split into `app.py` (HTTP routes), `logic.py` (business rules,
no database or HTTP), `store.py` (SQL) and `db.py` (connection and migrations).

## Run locally

Requires Docker. On Apple Silicon, enable Rosetta emulation in Docker Desktop
(SQL Server only ships for amd64).

```
docker compose up --build
```

- UI: http://localhost:8080
- maintenance: http://localhost:8001/health
- scheduling: http://localhost:8002/health

Compose starts SQL Server, then `db-init` (runs `db/init.sql`: one database
and one login per service), then both services. Each service waits for its
database and applies its migrations (`services/<name>/migrations/*.sql`) on
startup. Data is kept in the `sqldata` volume; `docker compose down -v`
deletes it.

Partial failure check: `docker compose stop maintenance`, then open the UI.
Lessons, students and instructors still load; tail numbers show as
"aircraft #N" and booking returns a clear "maintenance service is
unavailable" message. Screenshots are in `docs/evidence/`.

## Run one service on its own

```
docker compose up --build sqlserver db-init maintenance
```

## Tests

Per service:

```
cd services/scheduling        # or services/maintenance
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
ruff check . && ruff format --check .
pytest                        # fails under 70% coverage
```

Coverage is measured on the business rules (`logic.py`) and, for scheduling,
the HTTP client to maintenance (`maintenance_client.py`).

## Environment variables

| Variable | Service | Default | Purpose |
|---|---|---|---|
| `PORT` | both | `8000` | Port the service listens on |
| `DATABASE_URL` | both | none (secret) | `mssql+pymssql://user:password@host:1433/database` |
| `CORS_ORIGIN` | both | `http://localhost:8080` | The only browser origin allowed to call the service |
| `GIT_SHA` | both | `dev` | Version reported by `/health` |
| `MAINTENANCE_URL` | scheduling | `http://maintenance:8000` | Base URL of the maintenance service |
| `MAINTENANCE_TIMEOUT_S` | scheduling | `2` | Timeout for calls to maintenance |

The passwords in `docker-compose.yml` are throwaway defaults for the local
SQL Server container only. Override them in a gitignored `.env` file.
