# GENESIS → WebStudio Handoff (for OpenCode)

## What Genesis is
Autonomous software-engineering intelligence by Vrajhna Technologies (founder: Yuvraj Sharma).
Plain words in → verified full-stack software out (builds, runs, tests, repairs, verifies — proof, never claims).
Public repo: `https://github.com/vrajhna/PROJECT-GENESIS` (branch `main`, clean — no secrets).

## Where it lives
- Source of truth: `/home/yuvraj/Downloads/PROJECT GENESIS` (exact name, exact case).
- Frozen reference copy (do NOT touch): `/home/yuvraj/genesis`.
- Backend: `PROJECT GENESIS/backend` — Python + FastAPI, stdlib-first. API: `http://127.0.0.1:8000`.
- Frontend: `PROJECT GENESIS/frontend` — Next.js 14 + React 18, terminal-styled. Editor: `http://127.0.0.1:3101`.
- Secrets: ONLY in `PROJECT GENESIS/backend/.env` (`MODEL_API_KEY=...`). Gitignored, never zipped, never sent to any browser. If a key leaks anywhere, rotate it and tell the founder.

## What is done (all verified, none claimed)
- Spec → requirements → plan → questions (db/cache/payments, progressive) → full-stack build (frontend + API + SQLite + auth + tests) → live pytest → diagnosis → review → secure gate → VERIFIED report. Game kind too (canvas Snake + score API).
- Autopilot ON by default (safe steps run at once); push/deploy/delete/curl/rm always ask.
- Terminal with approval gate; CLI (`backend/genesis-cli/genesis`, stdlib-only, Linux/macOS/Windows): new/questions/build/download/chat/auto/upload/policy/status/serve.
- Playground full page (chat agent + code tabs, resizable, preview desktop/tablet/phone), boot animation, onboarding, local-profile login.
- Settings: Meta key paste (writes server `.env`), database sqlite/postgres with live `SELECT 1` probe.
- GitHub: live connection state (gh CLI as @vrajhna on this machine), public clone, guarded push (needs approval + `GITHUB_TOKEN`).
- Security fixed: project-id traversal guard, approval keeps exact argv, zips never follow symlinks, 300/min/IP rate limit, upload caps, zip-slip/bomb rejection, workspace confinement, shell=False everywhere.
- Suite: `82 passed, 1 skipped` (`python3 -m pytest tests/ -q` in `backend/`). Frontend: `npm run typecheck && npm run build` clean.
- Docs: `GUIDE.md` (manage/demo), `DEVELOPMENT_STATUS.md` (ledger), publish guide + pricing (Coming Soon) in the UI.

## What is left (in order)
1. Hosted Postgres URL → paste in playground Connect → verified (engine still files today).
2. Build queue + shared gate/rate store → then multiple API workers.
3. Server accounts (login is a local browser profile today).
4. One-click publish (export ZIP + DNS/Caddy guide exist; needs hosting credentials).
5. Billing switch (pricing page is Coming Soon + donate text).
6. `META_KEY_URL` env (console link for the key button), `GITHUB_TOKEN` env (push from server).

## Founder must provide (OpenCode: ask for these, don't invent)
- Hosting for `webstudiobhiwadi.com`: where Genesis runs (VPS Panel/docker), Tin Tak Lane address, whether Caddy/Nginx is available.
- DNS access for `genesis.webstudiobhiwadi.com` (A/CNAME).
- Hosted Postgres URL. Billing provider choice. Whether `main` may be deployed straight from GitHub.

## Rules for OpenCode (non-negotiable)
1. Work ONLY in `/home/yuvraj/Downloads/PROJECT GENESIS`. Never touch `/home/yuvraj/genesis`.
2. Never print, log, commit, or push `MODEL_API_KEY` or any token. `.env` stays local.
3. Never claim a feature works until it is executed and verified (run the suite; restart servers by exact PID; curl the endpoint).
4. Never overwrite user code without approval; use Git checkpoints/rollback.
5. Keep the terminal aesthetic (tiny mono, `$` sections). No purple gradients, no AI slop.
6. One milestone at a time; test before continuing: `python3 -m pytest tests/ -q`, `npm run typecheck`, `npm run build`.

## Prompt to paste into OpenCode
> I have a new project, GENESIS, in `/home/yuvraj/Downloads/PROJECT GENESIS` (public repo `vrajhna/PROJECT-GENESIS`, branch `main`). It is a working autonomous software-engineering platform (FastAPI backend on :8000, Next.js frontend on :3101, Python CLI) — read `GUIDE.md` and `DEVELOPMENT_STATUS.md` first, then inspect the tree. Your job: implement Genesis UNDER WebStudio Bhiwadi as fast as possible — serve it at `genesis.webstudiobhiwadi.com` (or the subdomain you recommend), wire the domain + hosting + Postgres, keep every existing feature working, and do it milestone by milestone with tests passing before you continue. Rules: never expose `backend/.env` or any key/token; never claim anything works without executing it; never overwrite working code without approval; ask me for hosting credentials, DNS access, Postgres URL, and billing choice instead of inventing them.
