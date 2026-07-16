# Repository Guidelines

Contributing guide for **recruitment-agent-2.0**, an AI recruitment assistant: a monorepo with a Python/FastAPI backend and a React/TypeScript frontend.

## Project Structure & Module Organization

~~~
backend/            # Python 3.11 FastAPI service (uv-managed)
  app/agent/        # base_skill, llm_adapter, skill_registry
    skills/<id>/vX_Y_Z/  # versioned YAML+prompt skills (jd_generation, resume_parsing)
  app/api/v1/endpoints/  app/core/  app/models/  app/schemas/  app/services/
  alembic/versions/ # DB migrations   tests/  # pytest (ASGI AsyncClient)
frontend/           # React 18 + Vite + Ant Design 5; src/{api,components,layouts,pages,services,store,types,utils}
docs/  ui/  docker-compose.yml  .env.example   # docs, HTML prototypes, infra (pgvector/Redis/MinIO)
~~~

## Build, Test, and Development Commands

**Infra:** `docker compose up -d` (Postgres, Redis, MinIO).

**Backend** (from `backend/`, uses `uv`):
- `uv sync` — sync deps.  `uv run uvicorn app.main:app --reload --port 8000` — dev server.
- `uv run alembic upgrade head` — apply migrations; `uv run alembic revision --autogenerate -m "<msg>"` — add one.
- `uv run pytest` — tests.  `uv run ruff check .` / `uv run ruff format .` — lint/format.

**Frontend** (from `frontend/`):
- `npm install` — deps.  `npm run dev` — Vite on :5173 (proxies `/api` to :8000).
- `npm run build` — `tsc -b && vite build`.  `npm run lint` — ESLint.

## Coding Style & Naming Conventions

- **Python:** Ruff, `line-length=120`, `py311`, rules `E,F,I,W,N,UP` (`E501` ignored). 4-space indent; `snake_case` modules/funcs/vars, `PascalCase` classes. Async-first (`async def` endpoints, SQLAlchemy async).
- **TypeScript:** `strict`, `noUnusedLocals`/`noUnusedParameters`. Use `@/` alias for `src/`. Components `PascalCase.tsx`; utils/hooks `camelCase.ts`. Prefer named exports.
- **Skills:** one dir per skill at `app/agent/skills/<skill_id>/vX_Y_Z/` with `skill.yaml`, `prompt.md`, optional `examples.yaml`. Bump the version dir on changes; the registry auto-loads the highest `v*`.
- **Migrations:** `<rev>_<snake_case_desc>.py`.

## Testing Guidelines

- **Backend:** pytest + `pytest-asyncio` (`asyncio_mode=auto`, `testpaths=["tests"]`) via the `client` fixture in `conftest.py` (httpx `ASGITransport`). Name files `test_<module>.py`, functions `test_<behavior>`. Mock async DB/LLM calls; cover new endpoints and services.
- **Frontend:** tests go in `frontend/tests/` — add a framework (e.g. Vitest) before introducing tests.
- Before pushing: `uv run pytest` and `npm run lint && npm run build`.

## Commit & Pull Request Guidelines

- **Conventional Commits** prefixes — `init:`, `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:` (e.g. `feat: add resume export endpoint`). Subject <= 72 chars; reference issues in the body.
- PRs must describe the change and why, list verification steps, note migrations or `backend/.env` additions, update `docs/` for API/data-model changes, and include screenshots for UI. Ensure `uv run pytest` and `npm run build` pass locally.

## Agent & LLM Notes

- Route LLM calls through `app/agent/llm_adapter.py` (`ChatOpenAI`, OpenAI-compatible). **Set `max_retries=0`** at both skill and adapter layers — layered retries stack timeouts.
- Do **not** pass `reasoning_effort` (the model rejects it); keep `LLM_MAX_TOKENS=4096`.
- FastAPI route order matters: define specific paths (e.g. `/{resume_id}/preview`) **before** `/{resume_id}`.
- Never commit `backend/.env` (gitignored). Copy `.env.example` and set `LLM_API_KEY`/`LLM_BASE_URL`.
