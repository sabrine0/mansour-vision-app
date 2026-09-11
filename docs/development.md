# Development

Everything in this document is verified against the repository as it stands. If a
command here does not work, that is a bug.

## Prerequisites

| Tool | Version | Why |
|---|---|---|
| Python | 3.11 | Every service. Not 3.12+ — the codebase is 3.11-compatible and CI pins it. |
| Node.js | 22 | The dashboard and the contract type generator. |
| Docker | 24+ with Compose v2 | The stack. |
| `make` | optional | Linux/macOS convenience. Windows developers use the equivalents below. |

## First run

```bash
# Python packages, editable, with their test extras
python -m venv .venv
.venv/bin/python -m pip install --upgrade pip                      # Windows: .venv/Scripts/python.exe
.venv/bin/python -m pip install -e packages/py-common[test] -e packages/contracts[test]
.venv/bin/python -m pip install -e services/core-api[test] -e services/vision-worker[test] \
                                 -e services/alert-engine[test] -e services/analytics-consumer[test]
.venv/bin/python -m pip install ruff mypy pytest-cov

# The npm workspace
npm install

# Local credentials Compose expects (never committed)
mkdir -p infra/secrets && openssl rand -base64 32 > infra/secrets/postgres_password

cp .env.example .env
```

With `make`: `make install && make secrets`.

## The commands you will actually use

| Task | With `make` | Directly |
|---|---|---|
| Everything CI runs | `make check` | see below |
| Python tests | `make test` | `.venv/bin/python -m pytest -m "not integration"` |
| Frontend tests | — | `npm run test` |
| Lint | `make lint` | `ruff check . && ruff format --check . && npm run lint` |
| Types | `make typecheck` | `mypy -p mansour_common -p mansour_contracts -p mansour_api -p mansour_vision_worker -p mansour_alert_engine -p mansour_analytics` &nbsp;·&nbsp; `npm run typecheck` |
| Autofix | `make format` | `ruff check --fix . && ruff format . && npm run format` |
| Regenerate contracts | `make contracts` | `python -m mansour_contracts.export --out packages/contracts/schema && npm run contracts:generate` |
| Start the stack | `make up` | `docker compose -f infra/compose/docker-compose.yml up -d --build` |
| Stop it | `make down` | `docker compose -f infra/compose/docker-compose.yml down` |
| Destroy its data | `make nuke` | `… down -v` |

**Two invocation details that will otherwise cost you an afternoon.**

`mypy` must be run **by package** (`-p mansour_common`), never by path. Each
package uses a `src/` layout, and given a path mypy resolves the same file under
two module names and refuses to continue.

`pytest` runs with `--import-mode=importlib` (set in the root `pyproject.toml`).
Three services legitimately have a `tests/test_service.py`; the legacy import
mode collides on the module name.

## Running a service outside Docker

Each service reads its configuration from the environment, prefixed by service:

```bash
# core-api on :8000, health on the same port
POSTGRES_HOST=localhost REDIS_HOST=localhost \
  .venv/bin/python -m mansour_api.main

# vision-worker: health only on :8080 until Milestone 3
WORKER_WORKER_ID=worker-1 REDIS_HOST=localhost \
  .venv/bin/python -m mansour_vision_worker.main
```

Every service answers `GET /healthz` (liveness — probes nothing) and
`GET /readyz` (readiness — probes its real dependencies). The distinction is not
cosmetic; see [`mansour_common/health.py`](../packages/py-common/src/mansour_common/health.py).

## The contract is generated, not hand-written

`packages/contracts` is the single source of truth for the event spine
(ADR 0007). The pydantic models are authoritative. From them:

```
events.py  ──►  schema/*.schema.json     (per-event validators)
           ──►  schema/spine.schema.json (bundled, shared $defs)
                        │
                        └─►  typescript/events.ts   (npm run contracts:generate)
```

CI runs both generators in `--check` mode. **A contract change that is not
propagated to both sides fails the build**, rather than failing at 2am on the
spine when a consumer meets a field it has never seen.

Never edit `packages/contracts/schema/` or `packages/contracts/typescript/` by
hand. Edit `events.py` and run `make contracts`.

## Two invariants the build enforces

**No copyleft dependency** (ADR 0002). `ultralytics` — YOLOv8, YOLO11 — is
AGPL-3.0, and its network clause would oblige us to publish the source of the
entire platform to every operator who logs in. The `license-gate` CI job and the
Docker build both fail if it, or any AGPL/GPL/SSPL package, appears. Detection is
RT-DETRv2 (Apache-2.0) via ONNX Runtime; tracking is ByteTrack via `supervision`
(MIT). Importing `ultralytics` for *any* purpose, even to export weights, brings
the obligation with it.

**No identifying field on any event** (ADR 0004).
[`test_privacy_invariants.py`](../packages/contracts/tests/test_privacy_invariants.py)
inspects every event model and its emitted JSON Schema, and fails if a field
appears that could identify, track, or characterise a person — `track_id` most of
all, because it is genuinely useful inside the worker and is one careless line
away from being published.

If one of those tests ever fails, remove the field. Do not amend the test.

## Secrets

Compose mounts credentials as **files** and exports `*_FILE` variables.
`mansour_common.config.read_secret` prefers that form. An environment variable is
visible in `docker inspect` and in `/proc/<pid>/environ`; a mounted file is not.
See [`infra/secrets/README.md`](../../infra/secrets/README.md).

Camera RTSP credentials never live in the database. `cameras.source_url` holds a
reference into the secret store — an RTSP URL with an embedded password is the
single most commonly leaked value in any CCTV deployment.

## Database migrations

Alembic lives in `services/core-api`. The URL is built at runtime from
`PostgresSettings`, so the password comes from the secret store and never lands in
a committed file.

```bash
make migration m="add cameras table"   # create
make migrate-sql                       # review the SQL without connecting
make migrate                           # apply
```

There are no migrations yet. The schema is Milestone 3.

## What exists today

Milestone 2 delivers the monorepo, the shared packages, the event contract, four
runnable and tested Python service shells, the dashboard, and the full local
stack. **The services start, report their health truthfully, and shut down
gracefully. They do not yet open a camera, run a model, or write a row** — and
they do not pretend to.
