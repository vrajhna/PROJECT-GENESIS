# PROJECT GENESIS — Architecture (0.1 foundation)

From specification to verified software. Generated code is not verified software.

## 0. Workspace reality (2026-11-02)

- Workspace root holds a SOLVO monorepo scaffold (`package.json` name `solvo`, `turbo.json`, `pnpm-workspace.yaml` → `apps/*`, `packages/*`).
- `apps/` does not exist yet at root. The working SOLVO code lives under `Documents/default-project/` (`packages/database`, `packages/ui`, `packages/contracts`, `apps/api`).
- Decision: do NOT overwrite SOLVO. GENESIS lives in `genesis/` as a separate service. It can later ingest SOLVO or any user repo (local path or GitHub) as a target project.
- Shell sandbox is broken in this session (`bwrap` missing / install under writable root). No command execution or test runs were possible here. All code below is written but marked UNVERIFIED until the sandbox is fixed.

## 1. Phase 1 vertical slice (what must work first)

```
USER SPEC → META REASONING → PLAN → CODE GEN → SANDBOX EXEC → TEST RESULT
```

Minimal path implemented in this drop:

- `backend/app/orchestrator/state_machine.py` — persistent-ready explicit states (CREATED … CANCELLED).
- `backend/app/spec/engine.py` — deterministic NL → structured requirements (no model needed for the slice).
- `backend/app/intelligence/meta_client.py` — centralized Meta Model API client, env-configured, runtime model check.
- `backend/app/intelligence/model_router.py` — Spark vs Wonder routing, no hardcoded IDs in callers.
- `backend/app/sandbox/exec.py` — stdlib subprocess sandbox placeholder (timeout, output caps, no shell) with Docker noted as next step.
- `backend/tests/test_meta_connection.py` — proves the connection path; skips cleanly without `MODEL_API_KEY`.

## 2. Module map (full system, built incrementally)

- Orchestrator: `backend/app/orchestrator/` — state machine, run manager, approvals gate.
- Specification: `backend/app/spec/` — requirements, acceptance criteria, plan artifacts.
- Architecture: `backend/app/architect/` (next) — ARCHITECTURE.md, DB schema, API contracts.
- Codegen: `backend/app/builder/` (next) — files, patches, git checkpoints.
- Execution: `backend/app/sandbox/` — this slice: local guarded exec; Phase 3: Docker non-root, limits, no creds.
- Testing: `backend/tests/` + `backend/app/testing/` (next) — pytest, coverage, Playwright later.
- Debugging/Repair/Verification/Memory: Phase 5–8, behind the verified slice.

## 3. Meta Model API integration (verified against docs, not yet called live)

- Base URL: `https://api.meta.ai/v1`, auth `Authorization: Bearer $MODEL_API_KEY`.
- Models (env-configurable, not hardcoded in callers): primary `muse-spark-1.3`, advanced `muse-wonder-1.0`.
- Endpoints used: `GET /v1/models` (connectivity check), `POST /v1/responses` (agentic calls).
- Rules: centralized adapter + router only; never expose key to frontend; explicit fallback only; record model, latency, tokens, errors per call.

## 4. Security baseline

- Generated code treated as untrusted. This slice never executes generated code on import; exec is opt-in with timeout and output caps.
- No host credentials in sandbox env. Destructive actions, deploys, external integrations require explicit approval (`WAITING_FOR_APPROVAL` state).
- Secrets only via env; `.env.example` lists names, never values.

## 5. What is deliberately NOT claimed

- No autonomous repair, no verification engine, no memory/benchmarks yet. Those are Phase 4–8 and stay marked incomplete until executed and tested.
