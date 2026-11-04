# PROJECT GENESIS — Vrajhna Technologies

Autonomous software engineering intelligence. From specification to verified software.

## What's in here

- `backend/` — FastAPI API, agent roles, tool registry, memory, improvement loop, DB schema, pipeline, 178-test suite
- `frontend/` — Next.js editor-style console (the studio workspace + spec docs part-i … part-ix)
- `ARCHITECTURE.md`, `IMPLEMENTATION_PLAN.md`, `GUIDE.md` — design, plan, user guide
- `.env.example` — copy to `.env` and fill `MODEL_API_KEY` for live model calls

Excluded on purpose (regenerated, never edited by hand): `frontend/node_modules/`, `frontend/.next/`, Python caches.

## Note for this machine

This folder lives inside Downloads alongside an unrelated loose web
scaffold (`../package.json`, `../postcss.config.js`). Genesis pins its
own `frontend/postcss.config.js`, so that scaffold can never break the
build again. Do not delete those neighbour files — they are not ours.

## Use it three ways

**1. Website** — https://genesis.webstudiobhiwadi.com (API: https://genesis-api.webstudiobhiwadi.com).
Log in, describe an idea or connect a repo, watch the agent crew build it live, publish to `/p/your-app`.

**2. Terminal, one command** (Linux / macOS / Windows with Python 3.8+, no packages needed):

```sh
curl -sSL https://genesis-api.webstudiobhiwadi.com/api/download/install.sh | sh -s https://genesis-api.webstudiobhiwadi.com
GENESIS_URL=https://genesis-api.webstudiobhiwadi.com genesis login
GENESIS_URL=https://genesis-api.webstudiobhiwadi.com genesis auto "Build me a website for my clothing business"
```

Windows (PowerShell): download `https://genesis-api.webstudiobhiwadi.com/api/download/install.ps1` and run it, then use `genesis` with `$env:GENESIS_URL` set the same way.

**3. Full engine on your machine** — `genesis serve` after downloading the engine pack (`<server>/api/download/engine`, `pip install fastapi uvicorn`). Same pipeline as the website: model writes it, Docker runs it, pytest proves it, repair fixes it.

## Run it from source (Linux)

Backend API (terminal 1):

```sh
cd backend
python3 -m pytest -q
python3 -m uvicorn app.api.server:app --port 8000
```

Frontend (terminal 2):

```sh
cd frontend
npm install                    # once
npm run build && npx next start -p 3101   # open http://localhost:3101
```

## What it does

Describe what to build in one sentence → the model designs the app (no templates, no keyword steering) → agents install, run, test, diagnose, repair and verify it in an isolated Docker sandbox → you get a live preview, a runnable ZIP, and one-click publish. Every claim in every report comes from executed evidence.

## License

MIT — see [LICENSE](LICENSE). © Vrajhna Technologies Pvt. Ltd.

Genesis is built by [WebStudio Bhiwadi](https://webstudiobhiwadi.com).
Generated applications carry no Genesis license restrictions.
