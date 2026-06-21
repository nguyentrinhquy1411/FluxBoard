# CPV Kanban AI

Real MVP monorepo for a TiDB-backed Kanban product with a read-only Groq/LangChain
AI analyst, FastAPI backend, and Vite React frontend.

## Quick Start

```powershell
uv sync --all-extras
npm install

# Configure secrets locally. Do not commit .env.
Copy-Item .env.example .env
# Fill CPV_TIDB_URL and GROQ_API_KEY in .env, then rotate any credentials shared in chat.

# Create the TiDB app schema/tables when ready.
uv run python -m app.database.migrate

# API
uv run uvicorn app.api:app --reload

# Web
npm run dev
```

## Verification

```powershell
npm run build
npm test
npm run lint
```

The API package lives in `apps/api/app`. The web app lives in `apps/web`.
Normal tests use in-memory/local data and do not touch TiDB.

Turbo runs both workspaces from the repo root:

```powershell
npm run dev    # API on 127.0.0.1:8000 and web on 127.0.0.1:5173
npm run build  # API import check and web production build
npm test       # Python + React tests
npm run lint   # Ruff + ESLint
```
