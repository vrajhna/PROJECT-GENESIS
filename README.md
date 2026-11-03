# PROJECT GENESIS — Vrajhna Technologies

Autonomous software engineering intelligence. From specification to verified software.

## What's in here

- `backend/` — FastAPI API, agent roles, tool registry, memory, improvement loop, DB schema, pipeline, 47-test suite
- `frontend/` — Next.js editor-style console (the studio workspace + spec docs part-i … part-ix)
- `ARCHITECTURE.md`, `IMPLEMENTATION_PLAN.md`, `DEVELOPMENT_STATUS.md` — design, plan, running ledger
- `.env.example` — copy to `.env` and fill `MODEL_API_KEY` for live model calls

Excluded on purpose (regenerated, never edited by hand): `frontend/node_modules/`, `frontend/.next/`, Python caches.

## Note for this machine

This folder lives inside Downloads alongside an unrelated loose web
scaffold (`../package.json`, `../postcss.config.js`). Genesis pins its
own `frontend/postcss.config.js`, so that scaffold can never break the
build again. Do not delete those neighbour files — they are not ours.

## Run it (Linux)

Backend API (terminal 1):

```sh
cd backend
python3 -m pytest -q            # suite: 47 passed, 1 skipped
python3 -m uvicorn app.api.server:app --port 8000
```

Frontend (terminal 2):

```sh
cd frontend
npm install                    # once
npm run dev                    # open http://localhost:3000
```

Or production: `npm run build && npx next start -p 3101`.

## Use it

Open the studio, create a project, describe what to build, press **Build, run, test, verify** — watch all 9 steps go green, then preview or download the ZIP. Never runs generated code without an isolated venv; never pushes or deploys without your approval.
