## 1. Backend framework: Flask
Date: 2026-10-02
Status: Decided
Context: Needed a backend framework for a single-process app with a small, well-understood surface (routes, SQLite, server-rendered pages). The comprehension check requires explaining every line cold.
Decision: Flask. Minimal and unopinionated — a route is a function, nothing is generated or hidden.
Alternatives considered: FastAPI, for typed request/response models and auto-generated docs. Rejected: neither feature pays for itself in a one-person, no-public-API app, and it's more surface to defend on paper than Flask buys back.
Consequences: No automatic request validation or docs — anything like that has to be written by hand if ever needed. In exchange, the whole request/response cycle fits in a few lines I wrote myself.

## 2. Two domains kept independently modularizable
Date: 2026-10-02
Status: Decided
Context: The assignment requires two backend feature domains coupled as little as possible, each able to point to where a future microservice split would go.
Decision: Scheduling and Maintenance live in separate packages (domains/scheduling, domains/maintenance) with their own service modules. Scheduling calls Maintenance only through one function, `is_airworthy(conn, aircraft_id)` — it never reads the aircraft/squawks tables directly.
Alternatives considered: Scheduling querying aircraft/squawk tables directly (join in SQL) to compute airworthiness inline. Rejected: it's less SQL, but it duplicates the grounding rule in two places and gives no single seam to cut along later.
Consequences: One extra function call per booking, and any new grounding rule only needs to change in one place (`is_airworthy`). The day this splits into two services, that function becomes the one HTTP call between them.
