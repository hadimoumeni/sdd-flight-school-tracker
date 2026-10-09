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

## 3. Lessons reference aircraft/students/instructors by foreign key, not duplicated data
Date: 2026-10-09
Status: Decided
Context: A lesson needs to know which student, instructor, and aircraft it's for, and the scheduling conflict check needs to query by instructor/aircraft efficiently.
Decision: `lessons` stores `student_id`, `instructor_id`, `aircraft_id` as foreign keys into `students`, `instructors`, `aircraft`. `squawks` stores `aircraft_id` as a foreign key into `aircraft`. No table duplicates another table's columns.
Alternatives considered: Storing a denormalized snapshot of student/instructor name on each lesson row (so the lesson record is self-contained even if the student is later renamed/deleted). Rejected: nothing in this app needs a lesson to survive a renamed or deleted student, and it would mean updating N lesson rows every time a student's name changes.
Consequences: Every lesson/squawk listing needs a JOIN to show human-readable names (see `domains/scheduling/routes.py`'s `index`). In exchange, there's exactly one place each piece of data lives.

## 4. Testing approach: business logic gets tests, routes get a manual run
Date: 2026-10-09
Status: Decided
Context: The assignment asks for ≥70% coverage on core business logic, explicitly excluding "framework glue or routing." Both domains' real logic (airworthiness, booking conflicts) lives in `service.py`; `routes.py` just reads a form, calls a service function, and redirects.
Decision: `domains/*/service.py` is unit-tested against an in-memory SQLite connection, built test-first (TDD): write the test, watch it fail, then write the minimum code to pass. `domains/*/routes.py` has no automated tests; each route was exercised once by hand over real HTTP (create student/instructor/aircraft, book a lesson, report a squawk, confirm a grounded aircraft rejects a booking) before being committed.
Alternatives considered: Using Flask's test client to write route-level tests too, for a higher overall coverage number. Rejected for now — it would mostly re-test the same conflict/grounding logic through an extra HTTP layer, for coverage on code the assignment doesn't grade.
Consequences: `pytest --cov=domains.maintenance.service --cov=domains.scheduling.service` reports 100%, honestly scoped to the code that's actually graded. If a route grows real logic of its own later, that logic should move into a service function and get the same test treatment — not stay untested in the route.
