# AGENTS.md

This file provides guidance to coding agents working in this repository.

## Language and collaboration

- All conversations, project documents, code comments, and user-facing error messages must use Chinese.
- Read relevant files before editing. For multi-module changes, present a plan before implementation.
- Do not modify comments outside the requested scope.
- The approved runtime stack is Vue 3 + Naive UI + FastAPI modular monolith.
- The online backend uses MySQL, Redis, and MinIO. Do not introduce RabbitMQ, a vector database, or another runtime dependency without explicit approval.

## Architecture

```text
Vue 3 frontend -> FastAPI modular monolith -> MySQL / Redis / MinIO / LLM
```

- `frontend/`: Vue 3, TypeScript, Vite, Naive UI.
- `agent-service/`: authentication, users, projects, files, Agent orchestration, LLM integration, and Alembic migrations.
- `deploy/`: local MySQL, Redis, MinIO, and optional RAG-profile middleware.
- `docs/`: long-lived architecture and interface documentation.

Python is the only writer of business tables. Alembic is the only schema owner. There is no Java runtime and no Java/Python business HTTP self-call.

## Protected Agent assets

Do not add, delete, move, rename, reformat, or rewrite these paths unless the user explicitly expands the scope:

- `agent-service/eval/**`
- `agent-service/training/**`
- `agent-service/normalization_demo/**`
- `agent-service/project_test/**`
- `agent-service/examples/**`

Keep existing `app.normalization` public symbols compatible because evaluation code imports them.

## Common commands

### Middleware

```bash
cp deploy/.env.example deploy/.env
docker compose --env-file deploy/.env -f deploy/docker-compose.yml up -d mysql redis minio
docker compose --env-file deploy/.env -f deploy/docker-compose.yml ps
docker compose --env-file deploy/.env -f deploy/docker-compose.yml down
```

Resetting volumes is destructive and requires confirmation:

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml down -v
```

### Python backend

```bash
cd agent-service
python -m venv .venv
source .venv/Scripts/activate
python -m pip install -e ".[dev]"
python -m alembic upgrade head
uvicorn app.main:app --reload --port 8000
python -m pytest
```

### Frontend

```bash
cd frontend
pnpm install
pnpm dev
pnpm typecheck
pnpm build
pnpm preview
```

Vite proxies `/api` to `http://localhost:8000`.

## Python backend conventions

- Business APIs use `/api/v1/<module>/<resource>`.
- Unified responses contain `code`, `message`, `data`, and `traceId`.
- Authentication uses Bearer JWT with Redis-backed `jti` sessions.
- Business modules live under `app/modules/<module>/` and contain API, schema, model, domain, repository, service, and error boundaries.
- API code must not access MySQL, Redis, MinIO, or LLM clients directly.
- Repository code must not call another repository or external infrastructure.
- Cross-module collaboration must use public Service interfaces.
- ORM models must not be returned directly as API responses.
- MinIO and LLM calls must not run inside database transactions.
- Agent tools may call module Services but must never receive an SQLAlchemy Session or execute model-generated SQL.
- High-risk actions require authorization, idempotency, traceability, and human confirmation.
- Database changes require a new Alembic revision; never rewrite an applied migration.

## Frontend conventions

- HTTP requests use `src/api/http.ts`, which injects `Authorization` and `X-Trace-Id`.
- Business code belongs in `src/modules/<module>/`.
- Protected routes rely on `useAuthStore()`.
- Use Naive UI, kebab-case file names, and PascalCase component names.
- After UI changes, run type checking and a production build. Validate key paths in a browser when runtime services are available.

## Git and documentation

- Use `main` plus task-scoped `feature/*` branches.
- Do not commit `node_modules/`, `.venv/`, `__pycache__/`, `.env`, generated data, or model artifacts.
- Update `docs/05-接口规范.md` for API changes, `docs/06-Agent设计.md` for Agent boundaries, and `deploy/README.md` for runtime changes.
- The latest approved design and `docs/21-Python单体后端迁移说明.md` override historical Java descriptions.
