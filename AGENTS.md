# AGENTS.md

## Cursor Cloud specific instructions

### Prerequisites

Docker must be running before any services can start. The VM environment requires Docker to be installed and the daemon started manually (`sudo dockerd` in background). The `.env` file at the repo root must exist with `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB` values (not committed to git).

### Starting the dev environment

```bash
docker compose up -d --build
```

Wait for the `crm-db` healthcheck to pass (the backend depends on it). The backend entrypoint automatically runs Alembic migrations and seeds, then starts uvicorn with hot-reload on `:8000`. The frontend Vite dev server runs on `:5173`.

### Running tests and checks

Commands per `CLAUDE.md` and `docs/dev.md`:

| Check | Command |
|-------|---------|
| Backend tests (45) | `docker exec crm-backend uv run pytest tests -q` |
| Frontend tests (29) | `docker exec crm-frontend npm run test` |
| Frontend lint | `docker exec crm-frontend npm run lint` |
| Frontend build | `docker exec crm-frontend npm run build` |

### Gotchas

- The frontend container runs as UID 1001. If `npm run build` fails with EACCES on `/app/dist`, run `docker exec -u root crm-frontend chown 1001:1001 /app` first. This only affects the production build, not dev mode or tests.
- Backend source is bind-mounted (`./backend:/app`), so code changes are picked up by uvicorn hot-reload automatically.
- Frontend source is bind-mounted (`./frontend:/app`) with a named volume for `node_modules`. If you add new npm dependencies, rebuild the container (`docker compose up -d --build frontend`) or `docker exec crm-frontend npm install`.
- System nginx is optional for development. Access services directly at `:5173` (frontend) and `:8000` (backend API).
- The `.env` file is not committed. Minimum required contents:
  ```
  POSTGRES_USER=postgres
  POSTGRES_PASSWORD=postgres_dev_pass
  POSTGRES_DB=app_db
  ```
