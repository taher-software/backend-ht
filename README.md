# Backend — Developer Guide

Quick reference for navigating the codebase and getting a local environment running.

---

## Stack

| Layer | Technology |
|---|---|
| API framework | FastAPI |
| ORM | SQLAlchemy (sync) + psycopg2-binary |
| Database | PostgreSQL (Cloud SQL on GCP) |
| Migrations | Alembic |
| Async jobs | Google Cloud Pub/Sub + Cloud Tasks |
| Caching / dedup | Google Cloud Firestore |
| AI | OpenAI API |
| Auth | JWT (Bearer token) |
| Server | Uvicorn |
| Infra | Terraform → Google Cloud Run |

---

## Local Setup

**1. Install dependencies**
```bash
pip install -r requirements.txt
```

**2. Create your env file**

Copy `.env.example` to `.env` (or `.envprod` for production) and fill in the required values:

```
db_url=postgresql+psycopg2://<user>:<password>@localhost/<db>
jwt_secret=<secret>
jwt_algorithm=HS256
jwt_access_expires=14400
openia_apikey=<openai-key>
mail_username=<email>
mail_pwd=<password>
worker_url=http://localhost:8000
```

**3. Apply database migrations**
```bash
alembic upgrade head
```

**4. Run the server**
```bash
ENV_FILE=./.env uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

The interactive API docs are available at `http://localhost:8000/`.

---

## Project Layout

```
src/
├── main.py                  # Entrypoint — calls start_app()
├── config.py                # App factory: middleware, exception handlers, router registration
├── settings.py              # Pydantic settings loaded from ENV_FILE
│
├── app/
│   ├── db/
│   │   ├── orm.py           # SQLAlchemy engine (NullPool) + SessionLocal + get_db()
│   │   ├── controller.py    # Generic dbController — find_by_id, find_by_field, etc.
│   │   └── models/          # One file per SQLAlchemy model
│   │
│   ├── gcp/
│   │   └── __init__.py      # Module-level singletons: pubsub_publisher, cloud_task_manager, firestore_client
│   │
│   ├── globals/
│   │   ├── authentication.py  # CurrentUserIdentifier (HTTPBearer dependency) + TTL token cache
│   │   ├── decorators.py      # @transactional — wraps service fn with DB session + auto commit/rollback
│   │   ├── response.py        # ApiResponse — standard response envelope for all endpoints
│   │   ├── schema_models.py   # Enums: Role, ClaimCategory, ClaimStatus, etc.
│   │   ├── enum.py            # JobType enum for async job dispatch
│   │   ├── error.py           # Reusable Error objects
│   │   └── exceptions.py      # ApiException
│   │
│   └── routers/             # One directory per domain (see Router Map below)
│       ├── __init__.py      # add_routers() — registers all routers on the FastAPI app
│       └── worker/
│           └── __init__.py  # Pub/Sub push receiver — dispatches jobs via JOB_HANDLERS table
│
└── async_jobs/
    └── tasks/               # One file per async job type
        ├── utils.py         # Shared helpers (e.g. get_concerned_namespaces)
        ├── daily_room_survey.py
        ├── restaurant_survey.py
        ├── room_reception.py
        ├── meals_notifs.py
        ├── add_meals_reminder.py
        └── assignment_reminder.py
```

---

## Router Map

Every router lives in `src/app/routers/<name>/` and follows the same file pattern:

| File | Purpose |
|---|---|
| `__init__.py` | Route definitions, auth checks, role guards |
| `services.py` | All business logic |
| `modelsIn.py` | Pydantic input models |
| `modelsOut.py` | Pydantic response models (when needed) |

| Router | Prefix | Description |
|---|---|---|
| `auth` | `/auth` | Login, token refresh, domain account confirmation |
| `users` | `/users` | Employee management |
| `guests` | `/guests` | Guest profiles |
| `rooms` | `/rooms` | Room management |
| `stays` | `/stays` | Guest stays |
| `housekeepers` | `/housekeepers` | Housekeeper profiles |
| `assignments` | `/assignments` | Housekeeper room assignments |
| `claims` | `/claims` | Guest claims / complaints |
| `surveys` | `/surveys` | Daily room and restaurant survey triggers |
| `menu` | `/menu` | Current meal menu for guests |
| `meals` | `/meals` | Meal and meal plan management |
| `dishes` | `/dishes` | Dish catalog |
| `chat` | `/chat` | Chat rooms and messages |
| `websocket` | `/ws` | WebSocket handler (TTS, real-time messaging) |
| `stats` | `/stats` | KPI and analytics endpoints |
| `namespace_settings` | `/namespace_settings` | Per-hotel configuration |
| `preferences` | `/preferences` | Guest preferences |
| `super_admin` | `/super_admin` | Cross-namespace admin actions |
| `worker` | `/` | Internal — receives Pub/Sub push messages |
| `health_check` | `/health` | Liveness probe |

---

## Authentication

All protected endpoints use:

```python
current_user: dict = Depends(CurrentUserIdentifier(who="user"))   # employees
current_user: dict = Depends(CurrentUserIdentifier(who="guest"))  # guests
current_user: dict = Depends(CurrentUserIdentifier(who="any"))    # either
```

`CurrentUserIdentifier` validates the `Authorization: Bearer <token>` header, decodes the JWT, and verifies the identity against the DB. Results are cached per token for 5 minutes (TTLCache) to reduce DB load.

Role-based access is checked manually in each endpoint:
```python
if not set(current_user.get("role", [])) & ALLOWED_ROLES:
    raise HTTPException(status_code=403, ...)
```

---

## Async Job System

Jobs are published to **Pub/Sub** and delivered via push to `POST /` (the worker router).

```
endpoint  →  pubsub_publisher.publish(JobType.X, payload)
                 ↓
          Pub/Sub push → POST /
                 ↓
          JOB_HANDLERS[job_type](payload)   # worker/__init__.py
                 ↓
          src/async_jobs/tasks/<handler>.py
```

To add a new job type:
1. Add the type to `JobType` in `src/app/globals/enum.py`
2. Create a handler in `src/async_jobs/tasks/`
3. Register it in `JOB_HANDLERS` in `src/app/routers/worker/__init__.py`

All handlers use `@backoff.on_exception(backoff.expo, Exception, max_tries=3)`.  
Firestore is used for deduplication (`PROCESSED_PUBSUB_TASKS` / `PROCESSED_CLOUD_TASKS` collections).

---

## Database Migrations

```bash
# Create a new migration after changing a model
alembic revision --autogenerate -m "describe the change"

# Apply all pending migrations
alembic upgrade head

# Roll back one step
alembic downgrade -1
```

---

## Infrastructure

Terraform configuration lives in `ci_cd/`:

```
ci_cd/
├── main.tf                        # Cloud Run services, Cloud SQL, Firestore, Cloud Scheduler
├── variables.tf                   # Variable definitions
└── modules/
    ├── cloud_run/                 # Reusable Cloud Run service module
    └── cloud_scheduler/           # Reusable Cloud Scheduler job module
```

```bash
cd ci_cd
terraform init
terraform plan
terraform apply
```

> **Note:** Never commit `terraform.tfstate` or `terraform.tfvars` — they contain secrets. Both are in `.gitignore`.

---

## Deployment

Use the `/deploy` skill from Claude Code — it commits, builds the Docker image, pushes it, and pushes to remote in one step.

Manual equivalent:
```bash
git add <files>
git commit -m "feature <name>: <description>"
echo "<sudo-password>" | sudo -S docker build --no-cache -t 77471580t/bodor_web_app:latest -f deployements/Dockerfile .
echo "<sudo-password>" | sudo -S docker push 77471580t/bodor_web_app:latest
git push origin main
```

