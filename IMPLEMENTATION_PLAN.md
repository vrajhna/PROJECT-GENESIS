# PROJECT GENESIS — Implementation Plan (Vrajhna Technologies, Meta × Cerebral Valley Hackathon)

## Goal for non-technical founders

Paste one prompt (or connect an existing GitHub repo). Genesis reviews code, connections, strings, and every integration a full-stack app needs, changes code only with the user's explicit approval, and repeats until requirements pass fully secured with no known vulnerabilities.

## Phase order (matches master spec, exact priority)

1. **Foundation (this drop):** state machine, spec engine, Meta client + router, guarded exec, connection test.
2. **Software generation:** workspace, file/patch tracking, git checkpoints, implementation reports.
3. **Execution:** Docker sandbox (non-root, CPU/mem/time limits, restricted mounts/net, no host creds).
4. **Testing:** pytest + coverage, API tests, Playwright, Ruff/Pyright, Bandit/pip-audit/secret scan.
5. **Debugging + repair:** structured diagnosis, minimal patches, bounded retries, rollback.
6. **Independent verification:** verified/failed/blocked/untested report. Never mark untested as passed.
7. **Interface:** Command Center → Analytics (Next.js, real recorded data only).
8. **Memory + improvement:** Postgres experience store, skills with evidence, controlled experiments, human approval for critical changes.

## This drop (vertical slice) — done in code, UNVERIFIED in execution

- [x] Orchestrator states: `backend/app/orchestrator/state_machine.py`
- [x] Spec engine: `backend/app/spec/engine.py` (+ artifacts SPECIFICATION.md / REQUIREMENTS.json shape)
- [x] Meta client: `backend/app/intelligence/meta_client.py` (env config, `/models` check, `/responses` call)
- [x] Router: `backend/app/intelligence/model_router.py` (routine → Spark, complex → Wonder)
- [x] Guarded exec: `backend/app/sandbox/exec.py`
- [x] Connection test: `backend/tests/test_meta_connection.py`
- [ ] Run pytest (BLOCKED: shell sandbox broken, see DEVELOPMENT_STATUS.md)

## Next milestones

1. Fix execution sandbox (install `bwrap` / move CLI outside writable root), then run `python -m pytest` in `genesis/backend`.
2. Set `MODEL_API_KEY`, run connectivity check, record latency in `model_calls` log.
3. Builder: file creation + `apply_patch` + git checkpoint behind approval gate.
4. Docker execution service per spec Part V/VII security controls.
5. Demo project (project-management app) per Part XVI, with a deliberately introduced defect repaired on camera.

## Non-goals for 0.1

No auto-deploy to public production, no silent model switching, no invented stats or fake green tests, no AGI/ASI claims.
