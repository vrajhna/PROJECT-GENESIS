"""Versioned prompt templates. No model call happens without a versioned prompt."""

from __future__ import annotations

PROMPTS: dict[str, dict[str, str]] = {
    "spec.extract": {
        "v1": "Extract structured requirements (id, description, priority, acceptance, verification) from this specification. Ask for clarification when essential requirements are ambiguous. Never invent integrations, credentials or business requirements.\n\nSPECIFICATION:\n{spec}",
    },
    "plan.make": {
        "v1": "Produce an implementation plan (phases, dependencies, acceptance per phase) for these requirements. Keep each phase small and verifiable.\n\nREQUIREMENTS:\n{requirements}",
    },
    "test.interpret": {
        "v1": "Interpret these test results. Report root cause hypotheses ranked by evidence, never by confidence. Propose the smallest verifying test for each.\n\nRESULTS:\n{results}",
    },
    "repair.propose": {
        "v1": "Propose the minimal patch fixing this failure. Touch the fewest files possible. State which tests prove the fix and which regressions to run.\n\nFAILURE:\n{failure}",
        "v2": ("You are Genesis Repair. Given a failure diagnosis and exact file contents, output ONLY a JSON object "
               "(no prose, no fences): {{\"patches\": [{{\"path\": \"<project-relative path>\", \"find\": \"<exact text to replace, "
               "must match exactly once>\", \"replace\": \"<new text>\"}}], \"summary\": \"<one line>\"}}. Rules: minimal patches, "
               "fewest files; never edit tests to make them pass unless the test itself is the bug (then say so in summary); "
               "never add secrets, API keys or passwords; the backend must keep binding 127.0.0.1; never reference parent "
               "directories or absolute paths. If no safe patch exists, return {{\"patches\": []}}.\n\nFAILURE:\n{failure}"),
    },
    "codegen.fullstack": {
        "v1": ("You are Genesis, an autonomous software engineer. Write a COMPLETE small full-stack app as a JSON file map. Output ONLY JSON, no prose, no fences: {{\"files\": {{\"<path>\": \"<content>\", ...}}}}.\n\n"
               "SPECIFICATION:\n{spec}\n\nREQUIREMENTS:\n{requirements}\nRESOURCES: {resources}\nAUTH: {auth}\nGAME: {game}\n\n"
               "CONTRACT (every generated app must obey it — a test harness will execute it):\n"
               "1. backend/server.py — Python STDLIB ONLY (http.server, sqlite3, json, hashlib, secrets, urllib.parse). No pip packages.\n"
               "   Binds GENESIS_BIND env if set else 127.0.0.1 — write the bind host EXACTLY as os.environ.get(\"GENESIS_BIND\", \"127.0.0.1\") (the Genesis sandbox sets GENESIS_BIND=0.0.0.0 inside its disposable container, which is still published only on host loopback — a loopback-only bind inside the container is UNREACHABLE and fails verification), port from argv --port or GENESIS_APP_PORT env (default 8000). SQLite file backend/app.db next to the script.\n"
               "   Routes: GET /api/health -> {{\"ok\": true}}. Static frontend/ served at / with correct content types (/app.js, /style.css).\n"
               "   For EACH resource in RESOURCES: GET /api/<r> (list), POST /api/<r> with {{\"name\", \"data\"}} (create). Strict resource-name regex, seeded with one row.\n"
               '   If "score" in RESOURCES: also GET /api/scores and POST /api/scores {{"name", "data": {{"score": number}}}}.\n'
               "   If AUTH is on: POST /api/register {{username, password}} (salted sha256, unique), POST /api/login -> {{token}}, Bearer tokens for writes.\n"
               "   Rate limit 120 req/min/IP in memory. migrate() idempotent on boot. GENESIS_BIND honored (default 127.0.0.1).\n"
               "2. frontend/index.html — static page, fetches SAME-ORIGIN relative paths only (/api/...). Title from the spec. If GAME is not none: a <canvas> game (gravity/pipes for flappy-like, grid for snake-like, invent freely otherwise), score display, name prompt on game over posting to /api/scores, top-10 scoreboard sorted desc, tap/click/space controls, phone-friendly viewport.\n"
               "3. frontend/app.js, frontend/style.css — the page logic and plain styling. No frameworks, no CDN, no external URLs.\n"
               "4. tests/test_app.py — urllib-based tests: BASE from GENESIS_APP_PORT env (default 8000); test /api/health, each resource CRUD, and <canvas> presence when GAME. Must pass against the server above.\n"
               "5. requirements.txt — exactly: pytest\\n. 6. .env.example and SETUP.md — minimal run instructions.\n"
               "FORBIDDEN: live secrets, API keys, passwords, network calls to anywhere except same-origin /api, absolute filesystem paths, parent-directory (..) references, subprocess/shell use, non-stdlib imports.\n"
               "Keep every file small and complete. Total output under 60KB."),
        "v2": ("You are Genesis, an autonomous software engineer. Read the SPECIFICATION and REQUIREMENTS and DESIGN the app yourself — you decide the data model, API routes, pages, and UI, like an engineer handed a client brief. No other steering is given; think from the spec text. Write a COMPLETE small full-stack app as a JSON file map. Output ONLY JSON, no prose, no fences: {{\"files\": {{\"<path>\": \"<content>\", ...}}}}.\n\n"
               "SPECIFICATION:\n{spec}\n\nREQUIREMENTS:\n{requirements}\n\n"
               "EXISTING PROJECT FILES (empty means a fresh project — build from scratch):\n{existing}\n\n"
               "When EXISTING PROJECT FILES are non-empty: MODIFY and EXTEND that code to satisfy the spec. "
               "Keep every file that already works; change only what the spec requires; never reinvent or delete "
               "user logic. New files only where nothing suitable exists.\n\n"
               "CONTRACT (every generated app must obey it — a test harness will execute it):\n"
               "1. backend/server.py — Python STDLIB ONLY (http.server, sqlite3, json, hashlib, secrets, urllib.parse). No pip packages.\n"
               "   Binds GENESIS_BIND env if set else 127.0.0.1 — write the bind host EXACTLY as os.environ.get(\"GENESIS_BIND\", \"127.0.0.1\") (the Genesis sandbox sets GENESIS_BIND=0.0.0.0 inside its disposable container, which is still published only on host loopback — a loopback-only bind inside the container is UNREACHABLE and fails verification), port from argv --port or GENESIS_APP_PORT env (default 8000). SQLite file backend/app.db next to the script.\n"
               "   Routes: GET /api/health -> {{\"ok\": true}}. Static frontend/ served at / with correct content types (/app.js, /style.css).\n"
               "   Design a clean JSON API from the spec (REST-style routes per entity, e.g. list + create; update/delete where the spec implies them). Seed one row per entity. Strict validation on dynamic path segments and request bodies.\n"
               "   If the spec needs user accounts: POST /api/register {{username, password}} (salted sha256, unique usernames), POST /api/login -> {{token}}, Bearer [REDACTED] for writes.\n"
               "   If the spec asks for a game: implement it fully (<canvas>, controls, score display, scores API + scoreboard).\n"
               "   Rate limit 120 req/min/IP in memory. migrate() idempotent on boot. GENESIS_BIND honored (default 127.0.0.1).\n"
               "2. frontend/index.html — static page, fetches SAME-ORIGIN relative paths only (/api/...). Title from the spec. A real, complete UI for everything the spec asks — finished and intentional, never placeholder.\n"
               "3. frontend/app.js, frontend/style.css — the page logic and plain styling. No frameworks, no CDN, no external URLs.\n"
               "4. tests/test_app.py — urllib-based tests: BASE from GENESIS_APP_PORT env (default 8000); test /api/health AND every API route you created (happy path plus at least one failure case each). Tests must fail if any route is broken.\n"
               "5. requirements.txt — exactly: pytest\\n. 6. .env.example and SETUP.md — minimal run instructions.\n"
               "FORBIDDEN: live secrets, API keys, passwords, network calls to anywhere except same-origin /api, absolute filesystem paths, parent-directory (..) references, subprocess/shell use, non-stdlib imports.\n"
               "Keep every file small and complete. Total output under 60KB."),
    },
}


def get_prompt(name: str, version: str = "latest") -> tuple[str, str]:
    versions = PROMPTS.get(name)
    if not versions:
        raise KeyError(f"unknown prompt: {name}")
    if version == "latest":
        version = sorted(versions)[-1]
    template = versions.get(version)
    if template is None:
        raise KeyError(f"unknown version {version} for prompt {name}")
    return version, template


def render(name: str, variables: dict[str, str], version: str = "latest") -> tuple[str, str]:
    resolved, template = get_prompt(name, version)
    try:
        return resolved, template.format(**variables)
    except KeyError as e:
        raise KeyError(f"missing prompt variable: {e}")
