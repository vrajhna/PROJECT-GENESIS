# DEVELOPMENT_STATUS.md — PROJECT GENESIS

## Current phase: PHASE 1 — Foundation (in progress)

### Completed

- Inspected workspace: root is SOLVO scaffold (`package.json`, `turbo.json`, `pnpm-workspace.yaml`); working code under `Documents/default-project/`; no `apps/` at root; no prior Genesis code. Genesis placed in `genesis/` to avoid overwriting.
- Verified Meta Model API contract against official docs via web: base `https://api.meta.ai/v1`, `MODEL_API_KEY` bearer auth, `GET /models`, `POST /responses`, model IDs `muse-spark-1.3` / `muse-wonder-1.0`.
- Wrote architecture: `genesis/ARCHITECTURE.md`.
- Wrote plan: `genesis/IMPLEMENTATION_PLAN.md`.
- Wrote foundation code (UNVERIFIED — not yet executed):
  - `genesis/backend/app/orchestrator/state_machine.py`
  - `genesis/backend/app/spec/engine.py`
  - `genesis/backend/app/intelligence/meta_client.py`
  - `genesis/backend/app/intelligence/model_router.py`
  - `genesis/backend/app/sandbox/exec.py`
  - `genesis/backend/tests/test_meta_connection.py`

### Remaining

- Execute tests (blocked on sandbox), live Meta connectivity check (needs `MODEL_API_KEY`), builder, Docker sandbox, testing lab, repair, verification, UI, memory.

### Files created this session

- `genesis/ARCHITECTURE.md`, `genesis/IMPLEMENTATION_PLAN.md`, `genesis/DEVELOPMENT_STATUS.md` (this file), `genesis/.env.example`, backend files listed above.

### Tests

- None executed. Shell sandbox broken: `bwrap` missing capability, CLI installed under writable sandbox root `/home/yuvraj`. Every `bash` call fails before start. Fix: install system `bwrap` and move CLI install outside `/home/yuvraj`, then run `python -m pytest` in `genesis/backend`.

### Known defects / security concerns

- `exec.py` is a local guarded subprocess, NOT yet the Docker-isolated executor the spec requires. Do not run untrusted generated code with it in production.
- No secrets present. Key handling is env-only; never sent to frontend.

### Next tasks

1. Repair sandbox, run test suite, record results here.
2. Live `GET /models` check with real key; record latency/errors.
3. Implement builder with approval gate + git checkpoints.

## 2026-11-02 — vertical-slice closure attempt

### Frontend baseline (created, not executed)

- `genesis/frontend/package.json` (Next 14, React 18, TypeScript; `dev: next dev`, `build: next build`).
- `genesis/frontend/tsconfig.json`, `genesis/frontend/app/layout.tsx`, `genesis/frontend/app/globals.css`, `genesis/frontend/app/page.tsx`, `genesis/frontend/README.md`.
- Page: spec textarea + submit (local only) + six pipeline stages. No backend wiring yet; pending endpoint `POST /api/projects/:id/specification`.

### Backend test execution (PASSED 2026-11-02, escalated sandbox)

- Sandbox fix: default sandbox still lacks `bwrap`; one-shot `require_escalated` run approved and used. `python3 --version` → `Python 3.12.3`, `pytest 9.1.1`.
- Command: `python3 -m pytest tests/ -v` in `genesis/backend` → exit 0.
- Real output: `5 passed, 1 skipped in 0.28s` — `test_state_machine_contract`, `test_spec_engine_splits_requirements`, `test_router_picks_models_from_env`, `test_guarded_exec_captures_output`, `test_meta_missing_key_returns_informative_error` passed; `test_meta_connectivity_live` SKIPPED (no `MODEL_API_KEY`).
- End-to-end probe `/tmp/genesis_slice_probe.py` (throwaway, kept out of repo) printed real output: `CREATED -> SPECIFICATION True`; 2 requirements (`REQ-001` P0 auth, `REQ-002` P1); router `routine codegen → muse-spark-1.3`, `complex architecture planning → muse-wonder-1.0`; exec `{"ok": true, "exit_code": 0, "stdout": "genesis-ok\n"}`.

### Live Meta Model API check (not run — no key)

- `MODEL_API_KEY=unset` verified via env presence check (value never printed).
- Client behaves correctly without key: `{"ok": false, "error": "MODEL_API_KEY is not set"}` (from probe + passing error-path test).
- Contract remains docs-verified only: `https://api.meta.ai/v1`, `GET /models`, `POST /responses`, `muse-spark-1.3` / `muse-wonder-1.0`. Live call still needs a real key; rerun `python3 -m pytest tests/ -v` with the key set and record latency here.

## 2026-11-02 — Phase-2 builder (approval-gated) + live-key request

### Live Meta check status

- Asked user for `MODEL_API_KEY`; user chose to paste a key in their next message. Not yet received, so no live `GET /models` this turn. Suite rerun still skips it by design.

### Builder (new, all existing files preserved)

- `backend/app/builder/files.py` — workspace-confined create/read, traversal rejected, audit log.
- `backend/app/builder/patches.py` — exact single-match replacement; zero/multi-match raises.
- `backend/app/builder/checkpoints.py` — `git init/add/commit` sha checkpoints, `git reset --hard` restore (approval-gated).
- `backend/app/builder/approvals.py` — PENDING → APPROVED/REJECTED gate; restore/deploy must pass through it.
- `backend/tests/test_builder.py` — 6 tests (files, escape/overwrite, patch ok + rejections, checkpoint roundtrip w/ approval, gate lifecycle).

### Test run (real, escalated sandbox)

- `python3 -m pytest tests/ -v` in `genesis/backend` → exit 0, `11 passed, 1 skipped in 0.66s`. Only skip is `test_meta_connectivity_live` (no key).

### Still ahead (Parts V–XVI order)

- Docker sandbox (non-root, limits, no creds), pytest/Playwright lab, debugging + repair loop, independent verification report, full UI wiring, Postgres memory, demo project with introduced defect.

## 2026-11-02 — LIVE Meta verification (key supplied by founder)

- Key handling: used only as an in-memory env var for two commands; never
  written to any repo file, never printed. (Founder pasted it in chat — it
  lives in chat history; rotate it if it was ever shared further.)
- `pytest tests/test_meta_connection.py -v` with key → exit 0, live test
  PASSED (missing-key path test correctly skipped).
- Live `GET /models`: `ok True`, latency `1169 ms`. API lists 9 models
  including both configured IDs: `muse-wonder-1.0`, `muse-spark-1.3`
  (plus 1.2, 1.1, voice-transcribe, image, sam-3.1, contributor variants).
- Full suite with key: `11 passed, 1 skipped in 1.30s`.

## 2026-11-02 — Frontend rebuild (precision console, verified serving)

- Rebuilt `frontend/app/globals.css` (dark console system, hairlines,
  mono data type), `frontend/app/page.tsx` (spec console with local
  deterministic preview, verification ledger with RECORDED values only,
  pipeline stepper, module + acceptance tables), `frontend/app/lib/spec.ts`
  (TS mirror of `spec/engine.py`), `frontend/app/layout.tsx` (viewport
  theme-color), `frontend/README.md`, `package.json` (+@types/react-dom),
  `tsconfig.json` (+skipLibCheck, Next default).
- `npm install` → 27 packages ok. `npm run typecheck` → clean (remaining
  upstream Next-14 lib mismatches silenced via skipLibCheck). `npm run
  build` → static `/` route 2.87 kB, First Load 90.1 kB.
- Serving: `npx next start -p 3101` detached via setsid; health check
  `HTTP 200, 10475 bytes`, page contains GENESIS. Declared README URL (port 3000) is superseded — use port 3101 while
  this server lives (`npm run dev` default is 3000 for local use).

## 2026-11-02 — Part 1 homepage (digitalmeadow.studio style)

- Reference studied via fetch: editorial hero, path/menu nav, short
  sections, tech lists, site-wide trophy checklist + `Trophies [n/7]`.
- Rebuilt light `paper` theme: `globals.css`, `page.tsx` (hero, not-a-list,
  16-step lifecycle checklist with honest states → `Milestones [7/16]`,
  principle quote, spec console, tech lists, recorded-only ledger,
  trophy footer `[n/5]`), `lib/spec.ts` reused for parsing.
- `typecheck` clean, `build` static `/` 4.09 kB.
- Server swap: old build stopped (its two PIDs verified as this session's
  `next-server` via `ss`/`ps`, killed by exact PID after a `pkill -f`
  self-match scare — pattern now avoided), new build on 3101:
  `HTTP 200, 14062 bytes`, served HTML contains `Project Genesis` ×2 and
  `Trophies` ×1.
- Waiting on founder: Part 2 of the spec.

## 2026-11-02 — Part 2 editor pass (pixel-faithful to reference)

- Founder supplied two screenshots (homepage + approach page). Applied:
  green-tinted mono text, pale-green active file row, highlighted inline
  chips (`genesis/`, `DEVELOPMENT_STATUS.md`, API-confirm chip), nested
  `spec/` folder with queued parts, `Control Panel [+]` popover (rain
  toggle, theme, motion note), live FPS meter, `Trophies [n/5] [+]`
  expander, contact + `theme: dark` sidebar foot.
- `typecheck` clean, `build` static `/` 4.47 kB.
- Server swap by exact PID (ss → ps confirm → kill; no more `pkill -f`
  self-match): new build on 3101, `HTTP 200, 10325 bytes`, served HTML
  contains `Control Panel`, `Trophies`, `part-ii`.
- Note: ASCII rain is client-rendered canvas — absent from static HTML by
  design, animates in the browser; honors `prefers-reduced-motion`.

## 2026-11-02 — Part 3 sections 03–05 in full

- Founder pasted full text of engines 03 (Architecture), 04 (Code
  Generation), 05 (Execution). Page now carries the complete item lists,
  the `Generate:` doc group on 03, the `Security requirements` group on 05,
  and hard `rule` chips (validation, record-all/GIT/patch rules, Docker
  first, never execute on host).
- `typecheck` clean, `build` static `/` 7 kB. Server swapped by exact PID
  (98409): `HTTP 200, 22554 bytes`, served HTML contains
  `DATABASE_SCHEMA.md`, `Disposable execution environments`,
  `Avoid unnecessary full-file rewrites`.
- Awaiting the next Part 3 remainder.

## 2026-11-02 — Part 3 sections 06–07 in full (05 confirmed verbatim)

- Founder re-pasted 05 (identical to what is live — no change) plus full
  06 (Testing) and 07 (Debugging). Page now carries: 06 test categories,
  five `Integrate —` stack groups, the 7-field result-store group; 07
  collect list, the 9-field diagnosis group, and both hard rules (model
  confidence is not proof; execution evidence only).
- `typecheck` clean, `build` static `/` 7.29 kB. Server swapped by exact
  PID (99900): `HTTP 200, 27059 bytes`, served HTML contains `pytest-cov`,
  `Confidence estimate`, `Do not treat model confidence as proof`.
- Still to receive in full: 08 (Repair) and 09 (Verification).

## 2026-11-02 — Part 3 section 08 in full (07 confirmed verbatim)

- Founder re-pasted 07 (identical to live — no change) plus full 08
  (Repair). Page now carries the 11-step repair workflow, the 5-limit
  group, and both hard rules (actionable report on repeated failure;
  never an infinite loop).
- `typecheck` clean, `build` static `/` 7.44 kB. Server swapped by exact
  PID (100683): `HTTP 200, 28659 bytes`, served HTML contains
  `Roll back failed repairs`, `Maximum concurrent executions`,
  `Never enter an infinite repair loop`.
- Still to receive in full: 09 (Verification) — the last piece of Part III.

## 2026-11-02 — Functional core (tool, not portfolio) + 09 in full

- Founder asked the right question: showcase vs tool. Answer: the site
  is the showcase; the tool is `python3 -m app.run --spec ... --workdir`.
  New real backend this turn:
  - `intelligence/model_registry.py` — every call recorded (id, model,
    task, latency, ok/error, retries, tokens, cost); summary stats.
  - `intelligence/prompt_manager.py` — versioned prompts (spec.extract,
    plan.make, test.interpret, repair.propose v1); unknown prompt or
    missing variable raises.
  - `intelligence/meta_client.py` — request IDs, retry with backoff on
    429/5xx, token capture, registry recording; missing key stays an
    informative error; model never silently switched.
  - `agents/roles.py` — Architect (spec→reqs, asks on empty), Builder
    (scaffold+test+manifest), Testing (real pytest, parses output),
    Reviewer (secret scan, no-tests→no-pass rule), Debugger (9-field
    diagnosis).
  - `app/run.py` — STATES walked through the real state machine;
    verdict VERIFIED only on tests-passed + review-clean.
- Suite caught a real contract bug: TESTING→REVIEW was an illegal
  transition; state machine fixed (test kept, machine corrected).
- Backend suite: `20 passed, 1 skipped`. CLI proven on the real entry
  point: 9 states to COMPLETED, `2 passed`, review clean, exit 0.
- Page 09 expanded to all 9 checks + both rules. `typecheck` clean,
  `build` 7.51 kB. Server swapped by exact PID (101874): `HTTP 200,
  29202 bytes`, markers confirmed. Part III page now complete 01–09.

## 2026-11-02 — Part IV remainder + full Part V agents + Part VI registry

- Part IV remainder needed no new code (meta_client/router/registry/
  prompts already implement every listed item); page part-iv already
  covers it.
- Backend: TestingAgent gained interpretation (failed-test names),
  coverage (pytest-cov when installed, honest pending note otherwise),
  regression diffing against `.genesis/last_failures.txt`; new
  MemoryEngine (JSONL lessons with evidence, kind-validated);
  new `tools/registry.py` — 14 tools, schema + permission validated,
  audit-logged, argv-only execution, approval-gated shell/restore.
- Suite caught 2 more real bugs (search excluded .txt; regression marker
  rewrite on empty state) — implementations fixed, tests kept.
  Suite: `28 passed, 1 skipped`.
- Page: part-v now 6 agents with backend mappings (Testing/Reviewer
  partial, rest live); new `part-vi — tool registry` doc (default);
  trophies `[n/9]`.
- `typecheck` clean, `build` 9.74 kB. Server swapped by exact PID
  (105093): `HTTP 200`, part-vi markers in HTML, Memory Engine confirmed
  in client bundle.

## 2026-11-02 — Parts VII + VIII + IX (memory, improvement, schema)

- Backend: `memory/` (service quarantining suggestions until execution
  confirms them, append-only store, trial-gated skill registry, keyword
  retrieval — no vector DB); `improve/experiments.py` (isolated-copy
  evaluation, baseline vs candidate, critical-path approval gate, real
  tree never touched); `db/schema.py` (18 entities, UUID PKs, UTC,
  FKs, indexes, validator + Postgres DDL generator).
- Suite caught 1 more real bug (substring mismatch in the new critical
  test's expectation — expectation corrected, implementation stood):
  `36 passed, 1 skipped`.
- Page: part-vii (10 kinds, 4 files, 8 skill fields, 2 rules), part-viii
  (7 areas, 10-step process, 2 rules), part-ix (18 entities, 9
  conventions marked partial pending Postgres wiring). Trophies [n/12].
- `typecheck` clean, `build` 11.3 kB. Server swapped by exact PID
  (106780): `HTTP 200`, part-ix markers in HTML, vii+viii confirmed in
  client bundle.
- Honest pending: live SQLAlchemy models, Alembic migrations, running
  Postgres (needs server + deps).

## 2026-11-02 — Product pivot: workspace UX + real build pipeline

- Vision doc (use-case table, 5 surfaces, 7-step flow) received; gap
  analysis below drove this build instead of more showcase docs.
- Backend: `builder/pipeline.py` (scaffold → venv → pip install → start
  with health check → pytest → logs → diagnose on failure → review);
  `access/zips.py` (zip-slip/bomb-safe extract, filtered archive with
  SETUP notes); `access/github.py` (parse, public/file clone, branch,
  diff summary, test-before-change, approval+token-gated push, honest
  OAuth refusal); `api/server.py` (FastAPI: projects, spec, chat,
  build, tree/files, upload/download, github routes, SSE events,
  request IDs, error envelopes, CORS for the editor).
- Suite: `47 passed, 1 skipped` (2 real bugs caught: leftover line,
  wrong test assertion — both fixed, tests kept).
- Live HTTP proof (not TestClient): project → spec → build returned
  VERIFIED with all 9 steps ok, exit path clean.
- Frontend: new default `studio — workspace` (new project, describe,
  chat, ZIP upload, GitHub clone, local folder picker, activity feed,
  file viewer, tests/errors, live preview iframe, download, setup
  guide). Backend offline banner with start command.
- Running now: API on 8000 (`/api/health` ok), editor on 3101
  (`HTTP 200`, workspace markers in served HTML). `typecheck` clean,
  `build` 14.5 kB.

## 2026-11-03 — Canonical move: Downloads/PROJECT GENESIS

- Founder ordered: source lives in Downloads, work happens only there.
- Copied `/home/yuvraj/genesis` → `/home/yuvraj/Downloads/PROJECT GENESIS`;
  `diff -r` byte-identical (62 files), excluding regenerable
  `node_modules/.next/__pycache__/.pytest_cache`. `.env.example` included.
  New root `README.md` added.
- New location proven: backend suite `47 passed, 1 skipped`; `npm
  install` + `next build` green (14.5 kB route).
- Move exposed one real hazard: Downloads holds an unrelated loose
  scaffold whose `postcss.config.js` broke the Next build (config walks
  up). Fixed properly with a pinned project-local
  `frontend/postcss.config.js` (empty plugins). Collateral from the
  misdirected first install (stray `Downloads/node_modules`,
  rewritten `Downloads/package-lock.json`, fresh `Downloads/dist/`)
  was removed except the lockfile, which is a valid fresh resolve —
  disclosed to the founder.
- Both demo servers now run from the new home: API :8000, editor :3101
  (`HTTP 200`, workspace marker in served HTML).

## 2026-11-03 — Message 2: real workspace (dashboard, playground, terminal, intelligence)

- Backend: `GET /api/dashboard` (real project stats from disk, usage
  aggregates, honest GitHub-connect status), `POST /api/playground/run`
  (stdlib-only, 20s cap, optional save-as-project), terminal pair
  `POST .../terminal` → explanation + approval item, `POST
  .../terminal/approve` → argv-only execution (string commands rejected
  by schema with 422), `GET .../suggestions` (tests/secrets/docs/TODO/
  bloat signals from the real tree).
- Frontend studio: Dashboard (projects, usage, Open), Playground,
  Terminal (what/why/changes/risks/rollback + Approve/Reject), running
  for `GENESIS_DATA_DIR`; Intelligence (severity-ranked findings).
  Trophies [n/14].
- Suite: `51 passed, 1 skipped`. Live HTTP proof against the RESTARTED
  server (stale process had masked the new routes): dashboard lists the
  Smoke project, playground prints 42, terminal approval flow echoes
  smoke-live, suggestions report the empty project.
- `typecheck` clean, `build` 15.7 kB. Editor on :3101 re-verified
  (`HTTP 200`, all four new panels in served HTML); API on :8000.
- `/home/yuvraj/genesis` is frozen reference; all future work happens in
  `Downloads/PROJECT GENESIS`.

## 2026-11-02 — Part IV (full) + Part V (agents slice) + agentic payload

- Backend: `respond()` gained `tools`, `response_format`, `effort`,
  `stream` via pure `build_payload()` — tested offline, model never
  swapped. Suite: `21 passed, 1 skipped`.
- Editor: new docs `part-iv — meta models` (strategy, env, 4 created
  files, 8 tracked fields, rules) and `part-v — agents` (Architect,
  Builder, Testing with backend mappings; Testing marked partial, paste
  truncated). Tree extended, trophies `[n/8]`, default doc part-v.
- `typecheck` clean, `build` 8.84 kB. Server swapped by exact PID
  (103324): `HTTP 200`, part-v markers in HTML, part-iv strings confirmed
  in the client bundle.

## 2026-11-02 — Part 3 architecture doc (nine engines, one kernel)

- Founder pasted Part III sections 01–09, ending at Independent
  Verification Engine ("Do not mark untested requirements as passed").
- New default doc `part-iii` in the tree: all nine engines as numbered
  rows with honest per-engine states (7 partial, 2 queued, 0 claimed done
  without execution) plus an evidence chip per engine.
- Trophies extended to [n/6] with "Open part-iii".
- `typecheck` clean, `build` static `/` 6.64 kB. Server swapped by exact
  PID (96216 confirmed `next-server`, killed, port freed): new build on
  3101, `HTTP 200, 19844 bytes`, served HTML contains `Nine engines`,
  `Orchestration Kernel`, `Verification Engine`.

### Preserved

- All prior `genesis/` docs and backend code left intact; this entry only appends.
- Frontend start path `npm run dev` + `http://localhost:3000` is declared but NOT running and NOT reachability-checked here.

## 2026-11-03 — Message 3 hardening: choices-during-build + secure gate + transient-only retry

- Backend `app/builder/fullstack.py`: `build_fullstack(..., answers, max_attempts=2)`
  keeps working automatically on TRANSIENT failures only (timeout/health/pip/
  connection via `_is_transient`); deterministic failures (tests, review, secure,
  bad answers) stop fast with an actionable report — bounded, never an infinite loop.
  New `secure` gate step (`_secure_scan`): asserts localhost bind, no live-secret
  patterns, stdlib-only runtime deps, payments test-key placeholder.
  `report["attempts"]` now counted; `SCALE_HINT` narrowed (bare "users" no longer
  triggers the Redis question).
- API `app/api/server.py`: new `GET /api/projects/{pid}/questions` (progressive —
  store idea asks db+payments, blog asks db only); `POST /fullstack` accepts optional
  `{answers}` (400 on invalid values, backward-compatible with bodyless POSTs).
- Frontend `Workspace.tsx`: after Understand, renders stack-choice buttons with
  recommended ★ defaults + why-notes; choices are sent with the full-app build.
  Steps timeline shows the new `secure` step automatically.
- Tests: new `backend/tests/test_fullstack_choices.py` (6 tests: defaults/reject,
  progressivity, stack-per-answers, transient classification, secure-scan blocks,
  questions API + 400 path). Full suite: `62 passed, 1 skipped`.
  Live: store spec -> questions `[('db','sqlite'),('payments','none')]`, bad answers -> 400.
- Servers restarted by exact PID; backend `:8000 /api/health ok`, editor `:3101 HTTP 200`
  with `Build full app` / `Watch it work` markers in served HTML.

## 2026-11-03 — OpenCode M2: engine Postgres (files fallback intact)

- New `backend/app/db/pg.py`: DATABASE_URL-gated helpers, zero global state.
  `ensure_schema()` creates `genesis_kv`, `genesis_hits`, `genesis_experience`
  (IF NOT EXISTS, never destructive); kv get/set; hits insert/count/prune;
  experience insert/filtered-query/confirm (KeyError/ValueError semantics match
  the file store). Every helper fails soft; `available()` caches a 60s probe.
- `memory/experience_store.py`: new `PgExperienceStore` (same record/query/
  confirm contract, per-call connections, closes always). `MemoryService`
  uses it only when Postgres probes live, else the JSONL file — plus a
  degraded-confirm path that falls back to the file ledger instead of crashing.
- `api/server.py`: rate limiter now writes the shared `genesis_hits` window
  when Postgres is live (multi-worker ready), in-memory otherwise; Connect
  probe (`_pg_reachable`) also ensures the engine schema and says so.
- `requirements.txt`: `psycopg2-binary>=2.9` (matches the existing probe import).
- Tests: new `backend/tests/test_pg_store.py` — 13 passed on fakes (SQL shapes,
  lifecycle, fallback, shared-limiter paths); live roundtrip SKIPPED without
  DATABASE_URL (runs on Railway). Full suite: `95 passed, 2 skipped`.
- Servers untouched by the edits (running processes keep old code until a
  PID-exact restart): API `:8000 /api/health ok`, editor `:3101 HTTP 200`.
  Module import re-verified after the edits.

## 2026-11-03 — OpenCode M1: Railway deploy configs (images proven, not claimed)

- `frontend`: API base is env-driven —
  `process.env.NEXT_PUBLIC_GENESIS_API || "http://127.0.0.1:8000"` in
  `Workspace.tsx` and `page.tsx`. Local dev unchanged.
- `backend/app/api/server.py`: CORS origins now extend from
  `GENESIS_CORS_ORIGINS` (comma-separated) on top of the localhost defaults.
- `backend/Dockerfile` (uvicorn on `$PORT`, `GENESIS_DATA_DIR=/data`) and
  `frontend/Dockerfile` (build arg baked, `next start` on `$PORT`), plus
  `.dockerignore` files and `RAILWAY_DEPLOY.md` (2 services + Postgres plugin,
  variables, Volume, health checks, exact DNS table, verify steps).
- `.env.example`: `GENESIS_DATA_DIR`, `DATABASE_URL`, `GENESIS_CORS_ORIGINS`,
  `NEXT_PUBLIC_GENESIS_API` documented (values only, never secrets).
- Docker actually built and ran here: `genesis-api:verify` booted and served
  `/api/health ok` + honest sqlite fallback; `genesis-web:verify` served
  HTTP 200 with the production API base present in the client bundle.
  Both images/containers removed after proof.
- Docker caught one real gap: `python-multipart` was installed on this
  machine but missing from `requirements.txt`, so the container crashed on
  boot. Fixed (`python-multipart>=0.0.9`), image rebuilt, health re-verified.
- Frontend `typecheck` clean, `next build` green; affected backend tests
  (`test_access`, `test_pg_store`, `test_settings`, `test_workspace`):
  `28 passed, 1 skipped`. Full suite last green: `95 passed, 2 skipped`.

## 2026-11-03 — OpenCode M3a+M3b: server accounts + one-click publish (LIVE-proven)

- New `backend/app/auth/accounts.py`: email+OTP login, PaperOS-style.
  sha256-hashed 6-digit codes, 10-minute expiry, 5 tries then dead, 5 codes
  per 10 min per email, 30-day bearer sessions, stdlib smtplib mail
  (HTML+text). No SMTP env = honest 503, never a fake success. Storage:
  Postgres tables (`genesis_users/otps/sessions`, added to shared schema)
  with JSON-files fallback; codes/tokens never printed or logged.
- `server.py`: `POST /api/auth/request|verify`, `GET /api/me`,
  `POST /api/auth/logout`, bearer helper `current_member()` (never raises).
  Projects stamp `owner_email` when created logged-in; explicit
  `POST /api/projects/{pid}/claim` for legacy ownerless projects.
- Publish (auth-gated): `POST /api/projects/{pid}/publish` copies the built
  static `work/frontend/` (index.html required, 20 MB / 2000-file caps, no
  dotfiles/caches/venvs/symlinks) to `/data/published/{slug}/` (Volume =
  survives redeploys). Serves at `/p/{slug}/` with correct content types,
  SPA fallback, no directory listing, `..` trapped to 404. First publish
  claims legacy projects transparently (recorded in meta). `DELETE`
  unpublishes (owner only). Slug from name + id suffix, collision-safe.
- Frontend: studio account row (email → code → name, session in
  localStorage, logout), Publish live / Unpublish buttons next to
  Download ZIP, publish doc rewritten (one-click first, ZIP path kept),
  onboarding copy updated (server accounts are live).
- Tests: new `test_accounts.py` — 7 passed (full flow, try-limits, rate
  limit, ownership/claim, publish lifecycle incl. traversal + authz).
  Full suite: `102 passed, 2 skipped`. Typecheck + build clean.
- LIVE proof (local, exact-PID restarts): debug SMTP sink received a real
  MIME mail → code verified → token → /api/me → owned project → publish →
  public URL served (index/assets 200, SPA fallback 200, traversal 404).
  Editor restarted on :3101 with the new UI (Publish live marker confirmed
  in the client bundle).
- Caught while wiring: stray JS-isms in new Python (`String()`,
  `.toLowerCase`) — tests + live run found them, fixed, re-verified, swept.

## 2026-11-03 — Flappy fix (live-reported defects, both real)

- Defect 1: a "flappy bird" spec built the generic scaffold — `GAME_HINT`
  never matched flappy-family words, and the only game template was Snake.
  Fixed: hint list widened (flappy/flap/game over/scoreboard/high score/
  canvas game/bird game/playable/…) with the `cart` exclusion kept; new
  `FLAPPY_HINT` selects a dedicated Flappy template (canvas bird, gravity,
  pipes, collision, tap/click/space, die → name prompt → same `/api/scores`
  contract + scoreboard as Snake). Decision text + `report["flappy"]`
  follow the template. Rebuilds are marker-gated, user files untouched.
- Defect 2: the studio preview iframe pointed at a `127.0.0.1` build port
  that dies with the build (dead on Railway by design). Fixed: once
  published, the frame embeds the public `/p/{slug}/` URL instead
  (sandbox `allow-scripts allow-modals` so the score prompt works);
  opening a project restores its published link; new projects reset it.
- Tests: new `test_flappy_builds_with_flap_and_pipes` — flappy spec →
  VERIFIED, `report["flappy"]`, flap+pipe markers, canvas, score contract,
  Flappy decision. Snake test still green (no regression).
- Verified: 2 game tests + `test_fullstack_choices` green (`8 passed`);
  frontend typecheck + build clean.

## 2026-11-03 — Genesis proper: the MODEL writes the app (Wonder, full aggression)

- Founder correction, accepted: hardcoded game templates are a fallback, not
  Genesis. Genesis = any idea in → model writes the code → pipeline proves
  it → every stage visible. Templates stay for offline/no-key builds only.
- New `app/builder/codegen.py`: `generate_with_model()` asks the model for
  a complete app as JSON `{files: {path: content}}` and enforces the contract
  BEFORE writing: exact file set, paths confined (no `..`, no absolute),
  200KB/file + 400KB total caps, secret-pattern scan, `backend/server.py`
  must bind localhost. Any violation → template fallback, never a crash.
- Routing: task kind `"multi-file codegen"` hits `COMPLEX_HINTS`, so
  generation ALWAYS uses the advanced model (Wonder), never Spark.
  `META_ADVANCED_MODEL` env selects the exact Wonder variant with zero code
  change (e.g. a Wonder Full ID). Generation timeout floor raised to 120s.
- New versioned prompt `codegen.fullstack v1`: the full generated-app
  contract (stdlib backend, health/resources/scores/auth routes, static
  frontend with canvas game when asked, urllib tests, pytest-only deps,
  forbidden list). Literal braces escaped for `.format()`.
- `build_fullstack` now records `report["author"]` + a decision line:
  `author: model <id> (N files, Xms)` vs `author: offline template (reason)`.
  Shown in the studio timeline automatically. Pipeline steps unchanged —
  they prove model-written code exactly like template code.
- Tests: new `test_codegen.py` — 9 passed (Wonder routing recorded, contract
  rejections for traversal/secrets/missing/localhost, no-key fallback,
  extractor shapes; live test skipped without a key). Regression:
  fullstack + intelligence suites `21 passed, 1 skipped`.
- Proven locally with fakes only (no key on this machine). Live proof needs
  a key: Railway already has `MODEL_API_KEY` — run any build there and read
  the `author:` decision line.

## 2026-11-03 — M6a: private projects + delete (your screenshot, fixed)

- Logged-out sessions now see NOTHING: `GET /api/projects` and
  `/api/dashboard` return empty without a token. Logged-in members see
  their own projects plus unclaimed legacy ones (Claim button in the
  dashboard makes them private).
- New `DELETE /api/projects/{pid}` (auth + owner only; legacy must be
  claimed first — no silent deletes). Removes the project tree AND its
  published `/p/` copy + index entry. Path-traversal guarded.
- Dashboard rows gained Claim (unclaimed only) + Delete (confirm dialog);
  empty state tells guests to log in; login/logout re-scopes the list.
- Tests updated to the new contract (login via real OTP flow with fake
  mailer): `test_listing_is_private_and_delete_works` covers 401/403/
  claim-first/publish-cleanup. Full suite: `113 passed, 3 skipped`.
- Incidental find, disclosed: `backend/.env` holds a now-DEAD Meta key
  (401 invalid_api_key; status-only probe, value never shown/committed —
  gitignored, in zero commits). It made live tests run-and-fail in
  full-suite runs (collection-order skip evaluation). Suite above ran with
  the file temporarily aside (live tests skip honestly); file restored
  byte-identical. Founder: paste a fresh key into `backend/.env` (local)
  and refresh Railway `MODEL_API_KEY` when ready — then live tests + model
  codegen prove themselves.
