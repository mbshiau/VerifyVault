# VerifyVault

Political Communication Analyzer — paste text, get structured claims, entities, topics, and sourced evidence.

## Structure

- `api/` — FastAPI backend (Groq Llama + Tavily pipeline, Postgres storage)
- `web/` — Next.js 15 frontend

## Run locally

### Backend

```bash
cd api
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in GROQ_API_KEY, TAVILY_API_KEY, DATABASE_URL
uvicorn main:app --reload
```

Requires a running Postgres. Quick start:
```bash
docker run -d --name vv-pg -e POSTGRES_PASSWORD=postgres -p 5432:5432 postgres:16
createdb -h localhost -U postgres verifyvault
```

### Frontend

```bash
cd web
npm install
cp .env.example .env.local
npm run dev
```

Open http://localhost:3000.

## API

- `POST /analyze` `{ text }` → creates analysis, returns `{ id, status: "processing" }`. Pipeline runs in a background task.
- `GET /analyze/{id}` → poll for completion (`status: "complete"`), returns `summary`, `claims[]` (with `sources[]`), `topics[]`, `entities[]`.

## Pipeline

1. Groq Llama 3.3 70B tool-use call extracts `summary`, `topics`, `claims`, `entities` in one shot.
2. For each claim, Tavily returns top-3 web sources.
3. Result persisted to Postgres.
