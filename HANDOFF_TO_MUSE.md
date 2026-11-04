# GENESIS → Muse Handoff (read this first, then DEVELOPMENT_STATUS.md)

You are taking over GENESIS from OpenCode mid-flight. Everything below was
executed and verified, not claimed. Founder: Yuvraj Sharma (heyjaxn),
Vrajhna Technologies. Product: WebStudio Bhiwadi.

## What Genesis is

Autonomous software-engineering intelligence: plain words in → verified
full-stack software out (spec → requirements → plan → model writes code →
venv → live server → pytest → review → secure gate → VERIFIED → publish).
Proof, never claims. Public hackathon repo.

## Where things live

- Source of truth (work ONLY here): `/home/yuvraj/Downloads/PROJECT GENESIS`
- Frozen reference copy, NEVER touch: `/home/yuvraj/genesis`
- GitHub (public): `https://github.com/vrajhna/PROJECT-GENESIS`, branch `main`
- Backend: `backend/` — Python + FastAPI, stdlib-first, API on `127.0.0.1:8000`
- Frontend: `frontend/` — Next.js 14 + React 18, terminal-styled, editor on `127.0.0.1:3101`
- CLI: `backend/genesis-cli/genesis` (stdlib-only, works offline)
- Secrets: ONLY in `backend/.env` locally (gitignored, never committed, never
  zipped, never sent to any browser). Never print/log a key value anywhere.

## Live infrastructure (all real, all founder-managed)

- Website: `https://genesis.webstudiobhiwadi.com` (frontend service)
- API: `https://genesis-api.webstudiobhiwadi.com` (healthy, verified)
- Railway project: services `genesis-api` (root `backend`, Dockerfile,
  Volume at `/data`) + `genesis-web` (root `frontend`, Dockerfile, build arg
  `NEXT_PUBLIC_GENESIS_API=https://genesis-api.webstudiobhiwadi.com`) +
  Postgres plugin (real tables; `DATABASE_URL` auto-injected).
- Pushing to `main` auto-deploys BOTH Railway services. That is the publish
  path for code: commit → push → live in ~2 min.
- DNS (Hostinger zone for webstudiobhiwadi.com): `genesis-api` CNAME →
  Railway is CORRECT. `genesis` is currently BROKEN — points at Hostinger
  parking A records (site shows "Coming soon"); founder must replace with a
  CNAME to the web service's Railway target (Networking → DNS records).

## How generated-app publishing works (already built + proven)

- Studio → login (email OTP) → build → **Publish live →** → app is copied to
  the `/data` Volume and served at `https://genesis-api.webstudiobhiwadi.com/p/{slug}/`
  in seconds. Owner-only publish/unpublish. API: `POST /api/projects/{pid}/publish`,
  `DELETE` same path. From terminal you can drive the same live API with a
  member Bearer token (login via `/api/auth/request` + `/api/auth/verify`).

## Auth + modes (structural, do not regress)

- Website = 100% live: httpOnly cookie session `genesis_session`
  (SameSite=None, Secure on https), CSRF header `X-Genesis-CSRF: 1` +
  Origin check on cookie-authed writes, projects private per owner,
  NOTHING in browser localStorage (memory token fallback only).
- Laptop/terminal (no `DATABASE_URL`) = local mode: files, full local
  authority, NO login walls. This split is intentional — keep it.
- `/api/health` reports `mode` (server|local), `db`, and `meta` status.
  `GENESIS_REQUIRE_DB=1` on Railway makes the API refuse file-backed boot.

## Meta models — current truth (verified against official docs)

- Client is spec-correct: `https://api.meta.ai/v1`, Bearer auth,
  `GET /v1/models`, `POST /v1/responses` `{model, input}`, output_text.
- Generator model (writer): `META_ADVANCED_MODEL=muse-wonder-1.0`.
  Chat/primary: `META_PRIMARY_MODEL=muse-spark-1.3`. Other valid IDs:
  muse-spark-1.3-contributor, muse-spark-1.2(+contributor), muse-spark-1.1,
  muse-image-1.0, muse-voice-transcribe-1.0, sam-3.1.
- **Muse Wonder Full is Muse-Code-only — NOT on the Model API. No Full ID exists.**
- Codegen fallback chain: Wonder → (on 404/model_not_found) Spark →
  offline templates, with every tried model named in the report.
  Failures are LOUD: `report["model_error"]` + `MODEL GENERATION FAILED`
  decision + studio notice. Never silently call a template build "AI".
- Health: startup background check + `POST /api/settings/meta/check`;
  states: no_key / invalid_key / unreachable / models_missing / ok.

## Credential status (blocker — founder action, do not invent)

- Local `backend/.env` key: DEAD. Meta returns HTTP 401 invalid_api_key
  (proven live, repeatedly). Rotate/create a fresh key in the Model API
  dashboard and paste it into `backend/.env` + Railway `MODEL_API_KEY`.
- Railway key authenticates but gets 404 on `muse-wonder-1.0` (that key's
  catalog lacks Wonder) — Spark works there; chain handles it.
- A Railway key was visible in founder screenshots shared in chat: rotate it.
- After pasting a valid key: restart backend → `/api/health` meta must say
  `ok` → run any build → the §4 timeline must show `author: model …`.
  That is the ONLY accepted proof of model authorship.

## What was built (all verified; details in DEVELOPMENT_STATUS.md)

- Full loop: spec → requirements → questions (progressive) → build
  (frontend+API+SQLite+auth+tests) → live pytest → diagnosis → review →
  secure gate → VERIFIED. Game specs too (Flappy/Snake canvas + score API).
- Model-driven codegen (`app/builder/codegen.py`, prompt
  `codegen.fullstack v1`, contract gate before writing) with templates as
  offline fallback only.
- Live parallel orchestration: lanes (architect/planner/builder/live/
  debugger/review/secure/verify), background runs, SSE
  (`?stream=true`, `/build/stream`), studio agent cards (§4 live crew).
- Server accounts: email OTP (hashed codes, rate limits, sessions),
  Postgres tables (`genesis_users/otps/sessions/kv/hits/experience`)
  with JSON-file fallback; publishes index in Postgres.
- One-click publish (above), private projects + claim + delete,
  downloads (CLI zip, engine zip), terminal with approval gate,
  autopilot (safe steps auto; push/deploy/delete/curl always ask).
- Acceptance proof on file: "task management application" spec →
  VERIFIED, booted standalone, CRUD 201/200, generated tests 4/4
  (script `/tmp/genesis-acceptance.py`, log `/tmp/genesis-acceptance.log`;
  regenerate anytime).
- Test state: `137 passed, 2 skipped` (+2 live tests needing a valid key).
  Frontend typecheck + build clean. Latest commits: `bf69713`, `f48289e`,
  `e89c979`, `298b7d9` (see git log).

## Run / restart / verify (exact)

```sh
cd "/home/yuvraj/Downloads/PROJECT GENESIS/backend"
python3 -m pytest tests/ -q                      # full suite (~2 min)
python3 -m pytest tests/test_codegen.py -q       # one area
cd "../frontend" && npm run typecheck && npm run build
# restart API: kill exact PID on :8000 (ss -ltnp), then
python3 -m uvicorn app.api.server:app --port 8000 --host 127.0.0.1
# restart editor: kill exact PID on :3101, then (frontend/)
npx next start -p 3101
curl http://127.0.0.1:8000/api/health            # mode/db/meta
```

Never `pkill -f` (self-match hazard — happened once). Kill by exact PID
from `ss -ltnp`, confirm with `ps`, then start detached
(`setsid nohup … < /dev/null &`).

## Rules (non-negotiable)

1. Work ONLY in `/home/yuvraj/Downloads/PROJECT GENESIS`. Never touch `/home/yuvraj/genesis`.
2. Never print, log, commit, or push any key/token. `.env` stays local.
3. Never claim anything works without executing it (run it, curl it, show output).
4. Never overwrite/delete user work; git checkpoint before risky changes.
5. Keep the terminal aesthetic (tiny mono, `$` sections). No purple gradients, no AI slop.
6. One milestone at a time; tests green before continuing.
7. Do not redesign the frontend or add features unless the founder asks.

## Next, in order (when founder says go)

1. Valid Meta key → meta health `ok` → first model-authored build proof.
2. Founder fixes `genesis` DNS CNAME (site is parked until then).
3. Model-assisted repair: wire `repair.propose` (Wonder) into the failure
   loop — deterministic failures currently stop with an actionable report.
4. Build queue + shared store → multiple API workers.
5. Billing switch (Razorpay chosen; pricing page is Coming Soon today).

## Message to resume with (founder: paste this into Muse)

> Read HANDOFF_TO_MUSE.md and DEVELOPMENT_STATUS.md in
> /home/yuvraj/Downloads/PROJECT GENESIS first, then confirm: branch,
> latest commit, /api/health output, and meta status. Genesis is live on
> Railway (genesis-api healthy; website DNS parked at Hostinger until I
> fix the CNAME). Work in place, verify everything by execution, never
> expose keys, and wait for my next instruction before changing code.
