# Flask ToDo App
![Tests](https://github.com/georges1138/flask-todo-service/actions/workflows/tests.yml/badge.svg)

A multi-user ToDo web application built with Flask using a layered MVC-style architecture.

The application supports authenticated users, per-user Todo ownership, completion tracking, filtering and sorting, theme switching, and a service layer that keeps business logic separate from Flask request handling.

## Features

- User registration and login
- Session-based authentication
- Versioned REST API with Bearer token authentication
- Per-user Todo ownership
- Add, edit, delete, filter, and sort Todos
- Mark Todos as complete or reopen them
- Completion timestamps
- Light and dark themes
- Custom error handling
- Versioned PostgreSQL schema migrations with Flask-Migrate / Alembic
- Single-command Docker Compose environment with orchestrated migrations
- 56 automated pytest tests running against PostgreSQL, executed in CI on every push
- Per-user weekly completion statistics
- Cumulative completion rates

## Tech Stack

- **Python 3.12**
- **Flask** — routing, sessions, controllers, and application setup
- **Flask-SQLAlchemy / SQLAlchemy 2.0** — ORM and database access
- **PostgreSQL 16** — application and test database
- **Psycopg 3** — PostgreSQL driver
- **Flask-Migrate / Alembic** — database schema migrations
- **Gunicorn** — WSGI server used by the container image
- **Docker / Docker Compose** — containerized application, PostgreSQL, and migration orchestration
- **GitHub Actions** — continuous integration test runs
- **Jinja2** — server-rendered HTML templates
- **HTML/CSS** — user interface
- **pytest** — automated tests
- **uv** — dependency and environment management

## Project Structure

```text
.
├── app/
│   ├── controllers/       # Flask routes and request handling
│   ├── middlewares/       # Authentication and error handling
│   ├── migrations/        # Alembic migration environment and revisions
│   ├── models/            # SQLAlchemy database models
│   ├── services/          # Business logic and database operations
│   ├── static/            # CSS and static assets
│   ├── templates/         # Jinja2 templates
│   ├── app.py             # Flask application factory and entry point
│   └── config.py          # Application configuration
│
├── scripts/
│   └── init-test-db.sql   # Creates todo_test on first PostgreSQL initialization
│
├── .github/
│   └── workflows/
│       └── tests.yml      # CI: pytest against PostgreSQL 16 on every push
│
├── tests/                 # pytest test suite
├── Dockerfile             # Application image (uv install, non-root user, Gunicorn)
├── compose.yaml           # db + migrate + app orchestration
├── .dockerignore          # Build context exclusions
├── .env.example           # Environment variable template
├── pyproject.toml         # Project metadata and dependencies
├── uv.lock                # Locked dependency versions
└── README.md
```

### Architecture

The application separates responsibilities across several layers:

- **Models** define persisted data and relationships.
- **Services** contain business logic and database operations.
- **Controllers** handle Flask requests, sessions, redirects, and templates.
- **Templates** render the user interface.
- **Middleware** handles cross-cutting concerns such as authentication and error handling.
- **Alembic migrations** version and apply persistent database schema changes.

## Getting Started

Docker Compose is the recommended way to run this project. It starts PostgreSQL, waits for it to become healthy, applies all Alembic migrations, and then starts the application under Gunicorn.

### 1. Clone the repository

```bash
git clone https://github.com/georges1138/flask-todo-service.git
cd flask-todo-service
```

### 2. Set `SECRET_KEY`

`SECRET_KEY` is the only variable you need to supply. Compose refuses to start without it, and the application has no insecure fallback.

Generate a random secret:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Then put it in a `.env` file in the repository root, which Compose reads automatically:

```text
SECRET_KEY=paste-your-generated-secret-here
```

`.env` is git-ignored. You do **not** need to set `DATABASE_URL` for the Compose path — Compose injects the internal `postgresql+psycopg://todo:devpass@db:5432/todo` URL for you.

### 3. Start the stack

```bash
docker compose up --build
```

### 4. Open the application

```text
http://localhost:3001
```

To stop the stack, press `Ctrl+C`, or run `docker compose down`. Use `docker compose down -v` to also remove the PostgreSQL volume and start from a clean database.

### What Compose does

The three services run in a strict order, enforced by health and completion conditions rather than by sleeps or retries:

```text
db → healthy (pg_isready)
      ↓
migrate → flask db upgrade → exits successfully
      ↓
app → gunicorn on localhost:3001
```

`migrate` waits for `db` to report `service_healthy`, and `app` waits for `migrate` to report `service_completed_successfully`. The application container therefore never starts against an unmigrated schema.

The application listens on port `3000` inside the container and is published on host port `3001` (`3001:3000`).

### Manual local development

If you would rather run Flask directly on your machine, for example to use the reloader or a debugger, the manual path is still supported.

Install dependencies:

```bash
uv sync
```

Configure the environment:

**PowerShell:**

```powershell
$env:SECRET_KEY = "paste-your-generated-secret-here"
$env:DATABASE_URL = "postgresql+psycopg://todo:devpass@localhost:5432/todo"
```

**Linux/macOS:**

```bash
export SECRET_KEY="paste-your-generated-secret-here"
export DATABASE_URL="postgresql+psycopg://todo:devpass@localhost:5432/todo"
```
Start PostgreSQL. Compose is the simplest option, since it also creates `todo_test` for you:

```bash
docker compose up -d db
```

Apply migrations and run the application from inside `app/`:

```bash
cd app
uv run flask --app app db upgrade
uv run python app.py
```

The manually launched application listens on `http://localhost:3000`, not `3001`.

## Running Tests

Tests run against the separate PostgreSQL `todo_test` database, never the application `todo` database.

You no longer need to create `todo_test` by hand. `scripts/init-test-db.sql` is mounted into the PostgreSQL entrypoint directory, so Compose creates `todo_test` alongside `todo` when it initializes the database.

> **Note:** PostgreSQL only runs entrypoint scripts when the data directory is empty, so `todo_test` is created the **first time** the `postgres_data` volume is initialized. If you started the database before this script existed, recreate the volume with `docker compose down -v` followed by `docker compose up -d db`.

pytest runs from the host, so the suite still needs `TEST_DATABASE_URL`:

**PowerShell:**

```powershell
$env:TEST_DATABASE_URL = "postgresql+psycopg://todo:devpass@localhost:5432/todo_test"
uv run pytest -v
```

**Linux/macOS:**

```bash
export TEST_DATABASE_URL="postgresql+psycopg://todo:devpass@localhost:5432/todo_test"
uv run pytest -v
```
> **Note:** Compose publishes PostgreSQL on localhost:5432 so host-side Flask development and pytest can connect to the containerized database.

The current suite contains **56 tests** covering Todo ownership and CRUD behavior, completion-state rules, user registration and authentication, API token authentication, Todo API CRUD and authorization behavior, JSON error handling, and PostgreSQL-backed reporting behavior including weekly bucketing, cumulative completion rates, per-user window partitions, and scoped reporting.

The test fixture creates and drops its schema in `todo_test`, so **do not point `TEST_DATABASE_URL` at the application `todo` database**.

### Continuous Integration

GitHub Actions runs the full pytest suite on every push using a disposable PostgreSQL 16 service container. The workflow installs dependencies from `uv.lock` and runs:

```bash
uv run pytest -v
```

The workflow definition lives in `.github/workflows/tests.yml`.

## REST API

The application exposes a versioned JSON API alongside the server-rendered HTML interface.

Base URL:

```text
http://localhost:3001/api/v1
```

The examples below assume the recommended Docker Compose setup, which publishes the application on port `3001`. If you started the application manually with `uv run python app.py`, substitute port `3000`.

### Authentication

- API routes use Bearer token authentication rather than the browser session used by the server-rendered HTML interface.
- A client obtains an API token by sending its username, password, and a token name to `POST /api/v1/tokens`.
- The raw API token is returned only when the token is created, so clients should store it securely at that time.
- Only a SHA-256 hash of the token is stored in PostgreSQL; the raw token is not persisted by the application.

### Create an API token

Send valid user credentials and a descriptive name for the token:

```http
POST /api/v1/tokens
```

Required JSON fields:

- `username` — the username of an existing registered user.
- `password` — the password for that user account.
- `name` — a descriptive label that identifies the client or purpose of the token.

Example request:

```bash
curl -X POST http://localhost:3001/api/v1/tokens \
  -H "Content-Type: application/json" \
  -d '{
    "username": "exampleuser",
    "password": "example-password-not-real",
    "name": "local-development"
  }'
```

A successful request returns `201 Created` and a JSON response containing:

```json
{
  "token": "<raw-token-returned-once>",
  "token_id": 1,
  "name": "local-development"
}
```

The client must store the raw `token` value securely when it is returned because the application does not persist or display the raw token again.

### Using the token

Protected API routes expect the token in the HTTP `Authorization` header:

```http
Authorization: Bearer <token>
```

The Bearer token identifies the API user whose account and permissions apply to the request.

Example:

```bash
curl http://localhost:3001/api/v1/todos \
  -H "Authorization: Bearer <raw-token>"
```

If the `Authorization` header is missing or malformed, or the token is invalid or expired, the API returns `401 Unauthorized`.

### Todo endpoints

All Todo endpoints require Bearer token authentication.

| Method | Endpoint | Purpose | Success |
|---|---|---|---|
| `GET` | `/api/v1/todos` | List Todos belonging to the authenticated user. | `200 OK` |
| `GET` | `/api/v1/todos/<todo_id>` | Retrieve one Todo belonging to the authenticated user. | `200 OK` |
| `POST` | `/api/v1/todos` | Create a new Todo for the authenticated user. | `201 Created` |
| `PUT` | `/api/v1/todos/<todo_id>` | Replace the title and description of an existing Todo belonging to the authenticated user. | `200 OK` |
| `DELETE` | `/api/v1/todos/<todo_id>` | Delete an existing Todo belonging to the authenticated user. | `204 No Content` |
| `PATCH` | `/api/v1/todos/<todo_id>/completion` | Toggle an existing Todo belonging to the authenticated user between complete and incomplete. | `200 OK` |

### API authorization

For API requests, the authenticated user's identity is resolved from the Bearer token in the `Authorization` header rather than from a browser session.

Every Todo lookup, update, deletion, and completion change is scoped to the user identified by that token. A client can therefore access or modify only Todos belonging to the authenticated API user.

If a Todo ID belongs to another user, the API returns `404 Not Found`, the same response used when the Todo ID does not exist for the authenticated user.

Returning `404 Not Found` instead of `403 Forbidden` avoids revealing whether a Todo with that ID exists under another user's account. A `403 Forbidden` response could disclose the existence of another user's Todo even though the requesting user is not authorized to access it.

## Database Migrations

The project uses Flask-Migrate, backed by Alembic, to version PostgreSQL schema changes.

Under Docker Compose, migrations are applied automatically by the `migrate` service before the application starts, so no manual step is required to bring a fresh environment to the current schema.

To author a new revision, run the migration commands locally against the development database:

```bash
cd app
uv run flask --app app db migrate -m "Describe the schema change"
uv run flask --app app db upgrade
```

Generated migration files live in `app/migrations/versions/` and should be reviewed before they are applied.

## Design Decisions

**User ownership is passed into the service layer explicitly.** The server-rendered HTML controllers read `user_id` from the Flask session, while API controllers resolve the user from the Bearer token and use `g.user_id`. Both paths then pass the authenticated user ID into the same ownership-aware service layer rather than allowing services to depend directly on session or request authentication state. This keeps business logic easier to test, reusable across both interfaces, and less tightly coupled to Flask.

**`SECRET_KEY` and database configuration have no silent runtime fallback.** Missing configuration fails loudly instead of allowing the application to start with an insecure secret or an unintended database. Compose enforces the same rule at the orchestration layer with `${SECRET_KEY:?SECRET_KEY must be set}`, so the stack refuses to start rather than booting with a placeholder secret.

**Migrations are orchestrated as a separate one-shot service.** Running `flask db upgrade` in its own container, gated on a PostgreSQL health check and completing before the application starts, keeps schema migration out of the application's startup path and makes a failed migration a visible, non-zero exit rather than a silently degraded application.

**Development and test databases are isolated.** The application uses the `todo` PostgreSQL database, while pytest uses `todo_test`, created by the PostgreSQL initialization script. This prevents destructive test cleanup from touching development data and ensures tests run against the same database engine as the application.

**Todo completion stores both `completed` and `completed_at`.** The explicit Boolean keeps service and template logic easy to read, while the timestamp supports reporting. `TodoService.toggle_complete()` owns the invariant so reopening a Todo also clears its completion timestamp.

**Weekly counts can be produced with `GROUP BY`, but cumulative completion statistics need each weekly row to retain its own values while also carrying running totals across earlier weeks for the same user.** A window function handles that ordered, per-user accumulation without collapsing the result set.

## Security

`POST /api/v1/tokens` requires valid user credentials. Invalid credentials return a generic `401 Unauthorized` response without revealing whether the username or password was incorrect. Issued API tokens are stored only as hashes rather than as raw token values. The token-creation endpoint does **not** currently implement rate limiting, so high-volume credential attempts remain a known production-hardening gap; a production deployment should add a shared-backend rate limiter, such as Redis.

- Passwords are stored as hashes rather than plaintext.
- Todo operations are scoped to the authenticated user.
- Browser routes are protected by session authentication middleware, while `/api/` routes bypass session authentication and use Bearer token authentication.
- Session configuration requires an externally supplied secret key.
- Unauthorized Todo update, delete, and completion operations are rejected by the service layer.
- The application image runs as a non-root `appuser` rather than as root.
- The PostgreSQL credentials in `compose.yaml` are development defaults and are not intended for deployment.
