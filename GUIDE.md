# GENESIS — Guide

Small, plain, complete. Everything below is true of the tree in this folder.

## What we built

Backend (`backend/`, Python + FastAPI, stdlib-first):

- Spec → requirements → plan → code → venv → live server → pytest →
  diagnose → review → secure-gate → VERIFIED report. Every step real.
- Full-stack builder: frontend + API + SQLite + auth + tests, plus a
  `game` kind (canvas Snake + score API + scoreboard).
- Progressive stack choices (db / cache / payments) asked after Understand.
- Auto-retry on transient failures only (max 3, bounded, reported).
- Terminal with approval gate + autopilot mode (safe commands run at once;
  push/deploy/delete/curl always ask).
- Intelligence status (models/agents/tools/skills, no secrets), settings
  (Meta key paste → `.env`, database sqlite/postgres with live SELECT 1 probe).
- GitHub: real connection state (gh CLI / token), public clone, guarded push.
- Genesis CLI (`genesis-cli/`): stdlib-only, Linux/macOS/Windows —
  new/questions/build/download/chat/auto/upload/policy/status/serve.

Frontend (`frontend/`, Next.js, terminal-styled, tiny mono):

- Studio (dashboard, two-option start, chat, questions, build, files,
  preview, upload/GitHub/local, setup guide, playground mini, terminal,
  intelligence), full-screen playground (code/run/save/build/preview
  sizes/chat/connect), about, download, models, docs (parts i–ix).

## What's remaining

1. Hosted data: Postgres for the engine itself (generated apps already
   emit a postgres pack; engine store is files today).
2. Build queue + shared gate store (multi-worker API).
3. Server accounts (login is a local profile today).
4. One-click publish (export + DNS guide exist; needs hosting credentials).
5. Billing (pricing page is "coming soon" + donate placeholder).
6. Native mobile wrapper (web + CLI cover desktop/laptop today).

## How we manage everything

```sh
cd "PROJECT GENESIS/backend"
python3 -m pytest tests/ -q            # full suite (~4 min)
python3 -m pytest tests/test_x.py -q   # one area
cd "../frontend" && npm run typecheck && npm run build
# restart api: kill exact PID on :8000, then
python3 -m uvicorn app.api.server:app --port 8000 --host 127.0.0.1
# restart editor: kill exact PID on :3101, then (in frontend/)
npx next start -p 3101
```

Never claim green without running. Never commit/push without being asked.
Secrets live only in `backend/.env` (gitignored, never zipped).

## How we showcase it (5-minute demo)

1. Boot animation → onboarding → studio.
2. "Build me a playable snake game with a high-score board." → Understand →
   answer 1 question → Build → watch install/start/test/review/secure →
   VERIFIED → play it in preview, switch phone size.
3. Break it on purpose (rename a resource), rebuild, show diagnosis + fix.
4. Upload a ZIP (improve path) → inspect → plan → approve nothing destructive.
5. Download panel: CLI zip + engine zip. Models page: live counts.
6. Close: "Generated code is not verified software. Ours is — here's the log."
