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

Run once with my own account (`az login` with the IE account, `gh auth login`),
in Bash. `infra/setup.sh` contains exactly these steps and can be run as
`AZURE_LOCATION=<region> [SQL_LOCATION=<region>] ./infra/setup.sh`.
No password is ever written to a file: they are generated in the script and go
straight into GitHub secrets.

1. **Region.** Pick one from the subscription's allowed list
   (`az policy assignment list`, policy "Allowed resource deployment regions").
   The free SQL offer is not in every region, so the SQL server can use another
   one from the list (`SQL_LOCATION`).
2. **Providers and resource group.**
   `az provider register --namespace <ns> --wait` for `Microsoft.App`,
   `Microsoft.OperationalInsights`, `Microsoft.Sql`, `Microsoft.Storage`,
   `Microsoft.ManagedIdentity`; then `az group create --name rg-hmoumeni-ieu2024`.
3. **Pipeline identity.** `az identity create --name hmoumeni-ieu2024-github`;
   `az role assignment create --role Contributor --scope <resource group id>`;
   `az identity federated-credential create` for
   `repo:hadimoumeni/sdd-flight-school-tracker:ref:refs/heads/main` and for the
   numeric-id form of the same subject (issuer
   `https://token.actions.githubusercontent.com`, audience `api://AzureADTokenExchange`).
4. **SQL server and databases.** `az sql server create --name hmoumeni-ieu2024-sql`;
   firewall rule `0.0.0.0`–`0.0.0.0` (allow Azure services); `az sql db create` for
   `hmoumeni-ieu2024-maintenance-db` and `hmoumeni-ieu2024-scheduling-db` with
   `--edition GeneralPurpose --compute-model Serverless --family Gen5 --capacity 1
   --min-capacity 0.5 --use-free-limit --free-limit-exhaustion-behavior AutoPause
   --backup-storage-redundancy Local`.
5. **Database users.** Open the firewall to my IP, then in each database with
   `sqlcmd` (from the SQL Server Docker image): `CREATE USER <service>_user WITH
   PASSWORD = ...` (a contained user, so it cannot reach the other database) and
   add it to `db_ddladmin`, `db_datareader`, `db_datawriter`. Close the firewall again.
6. **GitHub secrets and variables.** `gh secret set` for `AZURE_CLIENT_ID`,
   `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, `SQL_ADMIN_PASSWORD`,
   `MAINTENANCE_DB_PASSWORD`, `SCHEDULING_DB_PASSWORD`; `gh variable set` for
   `AZURE_LOCATION`, `SQL_LOCATION`, `PREFIX`, `RESOURCE_GROUP`, `UI_STORAGE`.
   CD is skipped until `AZURE_LOCATION` exists.
7. **Read access for grading.** `az role assignment create --role Reader` on the
   resource group for amartini@faculty.ie.edu and bserra@faculty.ie.edu.

Everything else (Container Apps environment and apps, Log Analytics, storage
account and its static website) is created by the first CD run from
`infra/main.bicep`. That first run is expected to fail to pull the images, because
new GHCR packages are private: make both packages public in their GitHub settings
and re-run the job.

**Status:** not deployed. When I started the Azure setup on 21 November, my Azure
for Students subscription was *Disabled*, and the portal says it cannot be
reactivated ("Please contact Azure Support"). Everything above is written and
checked in CI (the Bicep compiles, `shellcheck` passes on the setup script); it
runs as soon as a working subscription is available.

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
