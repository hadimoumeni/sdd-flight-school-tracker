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

## Deployment to Azure

Live URL: **not deployed yet** (see the note at the end of this section).

Every push to `main` runs CI; when CI passes on that commit, `.github/workflows/cd.yml`:

1. builds both images and pushes them to GHCR tagged with the commit SHA
   (`ghcr.io/hadimoumeni/flight-school-<service>:<sha>`);
2. signs in to Azure as the managed identity `hmoumeni-ieu2024-github` through
   OpenID Connect (no Azure password stored anywhere);
3. deploys `infra/main.bicep` to `rg-hmoumeni-ieu2024`: Log Analytics, the Container
   Apps environment, both Container Apps (0 to 1 replicas), the SQL server with
   one serverless database per service (free offer) and the UI storage account;
4. writes `ui/config.js` with the deployed service URLs and uploads `ui/` to the
   storage account's `$web` container (static website);
5. calls `/health` on both services and fails the run if they do not return 200
   within 6 minutes (enough for a cold start plus a database resuming from pause).

| Resource | Name |
|---|---|
| Resource group | `rg-hmoumeni-ieu2024` |
| Container Apps environment | `hmoumeni-ieu2024-env` |
| Container Apps | `hmoumeni-ieu2024-maintenance`, `hmoumeni-ieu2024-scheduling` |
| SQL server / databases | `hmoumeni-ieu2024-sql` / `hmoumeni-ieu2024-maintenance-db`, `hmoumeni-ieu2024-scheduling-db` |
| UI storage account | `hmoumeniieu2024ui` |
| Pipeline identity | `hmoumeni-ieu2024-github` |
| Logs | `hmoumeni-ieu2024-logs` |

### Initial setup (once)

```
az login            # IE account, Azure for Students subscription
gh auth login
AZURE_LOCATION=<an allowed region> PROFESSOR_EMAIL=<email> ./infra/setup.sh
```

`infra/setup.sh` creates the resource group, the managed identity (Contributor on
the resource group only, trusted only for `main` of this repository), the SQL
server and databases, one login per service, and the GitHub secrets
(`AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`,
`SQL_ADMIN_PASSWORD`, `MAINTENANCE_DB_PASSWORD`, `SCHEDULING_DB_PASSWORD`) and
the `AZURE_LOCATION` variable. CD is skipped until that variable exists. After
the first CD run, make the two GHCR packages public (GitHub → Packages →
Package settings → Change visibility) so Container Apps can pull them.

**Status (21 Nov):** my Azure for Students subscription shows as *Disabled* and
the portal says it cannot be reactivated. I opened an Azure support ticket and
told the professor. Everything above is written and checked locally
(`az bicep build` passes with no warnings); it runs as soon as a subscription is
available.

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
