# Genesis on Railway (founder-runbook)

Two services + one Postgres plugin, all inside one Railway project
(next to the existing WebStudio services). Nothing secret lives in git —
keys are pasted in the Railway dashboard only.

## 0. What you get

| Surface | URL | Source |
|---|---|---|
| Website playground (studio, dashboard, terminal) | `https://genesis.webstudiobhiwadi.com` | `frontend/` |
| Public API | `https://genesis-api.webstudiobhiwadi.com` | `backend/` |
| Terminal + desktop downloads | download panel inside the editor (CLI zip, engine zip) | built by the API |
| Database | Railway Postgres plugin (`DATABASE_URL` auto-injected) | real tables, survives redeploys |

## 1. Postgres plugin

Railway project → **+ New → Database → Postgres**. Note its
`DATABASE_URL` (Variables tab). Both services below reference it.

## 2. Service `genesis-api` (backend)

- **+ New → GitHub Repo** → `vrajhna/PROJECT-GENESIS`, branch `main`,
  **Root Directory = `backend`**. Builder: Dockerfile (auto-detected).
- **Variables:**
  - `DATABASE_URL` = `${{Postgres.DATABASE_URL}}` (reference the plugin)
  - `GENESIS_DATA_DIR` = `/data`
  - `GENESIS_REQUIRE_DB` = `1` (website refuses to boot file-backed)
  - `MODEL_API_KEY` = paste the Meta key (same value as local `backend/.env`)
  - `META_ADVANCED_MODEL` = exact Wonder model ID for codegen (ask Meta dashboard; e.g. wonder-full ID if provided, else leave unset for the default)
  - `META_PRIMARY_MODEL` = exact Spark model ID for chat (leave unset for default)
  - `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM` = mailer for login OTPs (Gmail App Password works; vmail works too)
  - `GENESIS_CORS_ORIGINS` = `https://genesis.webstudiobhiwadi.com`
  - (`PORT` is injected by Railway automatically.)
- **Volume:** + New Volume, mount path `/data` (projects persist here).
- **Domain:** Settings → Domains → Custom Domain →
  `genesis-api.webstudiobhiwadi.com`. Railway shows the CNAME target —
  add it to DNS (section 4).
- Health check path: `/api/health` (returns `{"ok":true,...}`).

## 3. Service `genesis-web` (frontend)

- **+ New → GitHub Repo** → same repo/branch,
  **Root Directory = `frontend`**. Builder: Dockerfile.
- **Build arg** (Service → Variables → build args, or Settings):
  `NEXT_PUBLIC_GENESIS_API` = `https://genesis-api.webstudiobhiwadi.com`
  (baked into the JS bundle at build time — rebuild after changing it).
- **Domain:** custom domain `genesis.webstudiobhiwadi.com` → add its
  CNAME target to DNS (section 4).

## 4. DNS (founder adds these)

In the `webstudiobhiwadi.com` DNS panel, two CNAME records:

| Host | Target |
|---|---|
| `genesis` | the `genesis-web` Railway domain shown in step 3 |
| `genesis-api` | the `genesis-api` Railway domain shown in step 2 |

(Railway displays the exact target value per custom domain; copy it verbatim.
HTTPS certificates are issued automatically.)

## 5. Verify (proof, not claims)

1. `https://genesis-api.webstudiobhiwadi.com/api/health` → `{"ok":true}`.
2. Open the editor → Settings → Database → **Connect** with no URL typed:
   with `DATABASE_URL` set it must report postgres reachable + engine tables
   ready (the Connect endpoint runs `ensure_schema()` itself).
3. Studio → new project → build the Snake demo → VERIFIED, preview plays.
4. Terminal panel → run `experiments 1+1` → approval → output appears.

## 6. Notes

- One API worker for now (default uvicorn). Build queue is the next
  milestone before adding workers; run snapshots already persist to
  Postgres for history and cross-worker reads.
- Website state (accounts, sessions, projects, reports, runs, memory,
  rate limits, publishes) lives in Postgres — no file fallback when
  `GENESIS_REQUIRE_DB=1`. Only execution workspaces (build trees,
  Docker contexts, published static copies, ZIPs) live on the `/data`
  Volume. Laptop/terminal use (no `DATABASE_URL`, flag unset) keeps
  full file authority with no login.
- Local dev is unchanged: `:8000` + `:3101` with `GENESIS_DATA_DIR` unset
  (files) or `DATABASE_URL` set (tables).
