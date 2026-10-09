# Python Backend: Caching Service

## FastAPI Microservice // Caching service

A small FastAPI microservice that generates payloads from two lists of strings and caches the results of the "transformer function" in PostgreSQL, so repeated strings are never transformed twice.

**Stack**:

- FastAPI for the API endpoints
- SQLAlchemy 2.0 (async) with PostgreSQL (`psycopg` 3)
- Alembic for schema migrations
- pytest for tests
- Docker / Docker Compose for deployment
- uv for dependency management

## Quick start

Requirements: Docker with Docker Compose.

1. Create the environment file:

    ```bash
    cp .env.example .env
    ```

2. Start everything (database, migrations, API):

    ```bash
    docker compose up --build
    ```

3. The API is available at `http://localhost:8000`, and the interactive docs at `http://localhost:8000/docs`.

The `migrate` service applies the Alembic migrations once and exits. The `api` service starts only after it completed successfully.

To stop the services:

```bash
docker compose down      # keep the data
docker compose down -v   # also wipe the database volume
```

## Configuration

Settings are read from environment variables, or from a `.env` file when running locally.

| Variable | Description |
|---|---|
| `POSTGRES_USER` | Database user (used by the `db` container) |
| `POSTGRES_PASSWORD` | Database password (used by the `db` container) |
| `POSTGRES_DB` | Database name (used by the `db` container) |
| `DATABASE_URL` | SQLAlchemy URL used by the app and Alembic |

Inside Docker the database host is `db:5432`. When running the app or Alembic from your machine, use `localhost:5433`:

```
DATABASE_URL=postgresql+psycopg://<user>:<password>@localhost:5433/<db>
```

The container publishes Postgres on host port **5433** (not 5432) so it does not clash with a Postgres already installed on the host.

## API

### Create a payload

`POST /payload`

```json
{
  "list_1": ["first string", "second string", "third string"],
  "list_2": ["other string", "another string", "last string"]
}
```

Response:

```json
{
  "id": "3f7a...c91b"
}
```

Both lists must have the same length, otherwise the service responds with `422`.

### Read a payload

`GET /payload/{id}`

```json
{
  "output": "FIRST STRING, OTHER STRING, SECOND STRING, ANOTHER STRING, THIRD STRING, LAST STRING"
}
```

Unknown identifiers respond with `404`.

## Design decisions

- **Deterministic payload identifier**: the identifier is a SHA-256 of the two input lists, encoded as JSON. The same input always produces the same identifier, so reusing identifiers needs no extra bookkeeping. JSON encoding keeps `["a,b"]` distinct from `["a", "b"]`, and the order of the lists matters.
- **Per-string cache**: strings are deduplicated, looked up with a single query, and the transformer is called **once per request**, only for the strings that are not cached yet. If the whole payload already exists, the transformer is not called at all.
- **Hash as primary key**: the cache table is keyed by the SHA-256 of the source string, not the string itself. PostgreSQL limits the size of index entries, so a long input string as a primary key would make inserts fail.
- **Upserts**: inserts use `ON CONFLICT DO NOTHING`. Two concurrent requests with the same new string do not fail with an integrity error, because the transformer is deterministic and both compute the same value.
- **Atomic writes**: the cache rows and the payload row are committed together in one transaction.
- **Dependency injection**: the application structure is built around FastAPI's `Depends`. Each layer receives what it needs instead of creating it: the router gets a `PayloadService`, the service gets an `AsyncSession`, and the session is opened per request and closed afterwards by a `yield` dependency. No layer imports a concrete collaborator to instantiate it, so wiring lives in one place (`src/dependencies/`). This keeps the service independent of FastAPI and makes testing cheap: unit tests pass a mocked session straight to the constructor, and API tests swap the whole service through `app.dependency_overrides`.
- **Layering**: the service knows nothing about HTTP. It raises `PayloadNotFoundError`, and the exception handler in `main.py` translates it to a `404`.
- **Migrations own the schema**: tables are created by Alembic, not by `create_all`, and the `migrate` service runs separately so multiple API replicas never race on migrations.

## Project structure

```
.
├── alembic.ini
├── migrations/              # Alembic migration scripts
├── src/
│   ├── api/api_v1/          # FastAPI routers
│   ├── dependencies/        # Dependency injection providers
│   ├── resource_access/     # SQLAlchemy models
│   ├── schemas/             # Pydantic request/response schemas
│   ├── services/            # Business logic (PayloadService)
│   ├── config.py            # Settings
│   ├── database.py          # Engine and session factory
│   └── main.py              # FastAPI application
├── tests/
│   ├── unit/                # Service logic, session and transformer mocked
│   └── api/                 # HTTP contract, service mocked
├── docker-compose.yml
├── Dockerfile
└── pyproject.toml
```

## Development

Install dependencies:

```bash
uv sync
```

Run the database and apply the migrations:

```bash
docker compose up -d db
uv run alembic upgrade head
```

Run the API with auto-reload:

```bash
uv run uvicorn src.main:app --reload
```

Create a new migration after changing a model:

```bash
uv run alembic revision --autogenerate -m "describe the change"
uv run alembic upgrade head
```

Always review the generated migration before committing it.

## Tests

```bash
uv run pytest
```

- **Unit tests** cover the service logic: interleaving, identifier generation, and the caching behavior (the transformer is called only for deduplicated cache misses, and never when everything is cached). The database session and the transformer are mocked.
- **API tests** cover the HTTP contract: routing, validation (`422`), response shapes, and the `404` handler. The service is replaced through FastAPI's `dependency_overrides`, so these tests do not touch the database.

## Known shortcuts

- **No integration tests against a real database yet.** Because the session is mocked, the SQL itself (the `IN` lookup and the `ON CONFLICT` upserts) is not covered by automated tests. The natural next step is integration tests against a throwaway PostgreSQL (e.g. `testcontainers`).
- **`IN (...)` size.** The cache lookup sends one bound parameter per unique string. A request with tens of thousands of unique strings could hit PostgreSQL's limit of 65,535 parameters. Such requests would need chunking.
- **Transformer is a stand-in.** `PayloadService.transform` upper-cases the strings to simulate the external service. It is assumed to be deterministic, which is what makes the upsert race safe.
- **Credentials in compose and `.env.example`** are development defaults, not for production.
- **No cache eviction.** Cached results are kept indefinitely.