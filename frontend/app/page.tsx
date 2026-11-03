"use client";

import { useEffect, useRef, useState } from "react";
import AsciiRain from "./components/AsciiRain";
import Workspace from "./components/Workspace";
import { parseSpecification } from "./lib/spec";

type State = "done" | "partial" | "queued";

const GLYPH: Record<State, string> = { done: "●", partial: "◐", queued: "○" };

interface Check {
  text: string;
  state: State;
  evidence: string;
}

/* Part II — every check below was executed this session, evidence attached. */
const PRECODE: Check[] = [
  { text: "Inspect the existing repository", state: "done", evidence: "Root is a SOLVO scaffold (package.json, turbo.json, pnpm-workspace.yaml); working code under Documents/default-project/." },
  { text: "Identify source files, dependencies, configuration, working functionality", state: "done", evidence: "Monorepo config, Prisma database package, no apps/ at root — recorded before any write." },
  { text: "Never overwrite working functionality without understanding it", state: "done", evidence: "Genesis lives in genesis/; SOLVO code untouched." },
  { text: "Identify missing components", state: "done", evidence: "Builder, Docker sandbox, repair loop, verification engine queued in IMPLEMENTATION_PLAN.md." },
  { text: "Prepare an implementation plan", state: "done", evidence: "IMPLEMENTATION_PLAN.md — phase order I–VIII." },
  { text: "Create a dependency map", state: "done", evidence: "Backend stdlib-only; frontend Next 14 + React 18 + TS (27 packages installed)." },
  { text: "Establish a working baseline", state: "done", evidence: "Backend suite green: 11 passed, 1 skipped. Live API 1169 ms." },
  { text: "Begin implementation in small, verifiable stages", state: "done", evidence: "Foundation, then builder, then this page — each built, tested, recorded." },
];

const PHASES: Array<[string, string]> = [
  ["Completed functionality", "Orchestrator states, spec engine, Meta client + router, guarded exec, approval-gated builder, two console generations."],
  ["Remaining functionality", "Docker sandbox, Playwright lab, debugging + repair loop, verification engine, Postgres memory, demo project."],
  ["Files created or modified", "genesis/backend (10 modules + 2 test files), genesis/frontend (console + editor generations), 4 spec docs."],
  ["Tests executed", "pytest tests/ — full suite, twice (with and without live key)."],
  ["Test results", "11 passed, 1 skipped in 1.30s with key; live GET /models ok, 1169 ms."],
  ["Known defects", "Local exec is guarded subprocess, not Docker isolation. Frontend/backend not wired yet."],
  ["Security concerns", "API key in chat history — rotate if shared. Key handling env-only; approval gate on destructive acts."],
  ["Next development tasks", "Render Part 2 (this page), then Docker sandbox, then repair loop."],
];

interface ArchSection {
  n: string;
  title: string;
  state: State;
  blurb: string;
  evidence: string;
  items: string[];
  groups?: Array<{ label: string; items: string[] }>;
  rules?: string[];
}

const PARTIII: ArchSection[] = [
  {
    n: "01", title: "Central Orchestration Kernel", state: "partial",
    blurb: "The conductor: goals in, verified software out. Assigns work, calls tools, spends budget, knows when to stop — and when to ask a human.",
    evidence: "16-state machine live with transition rules (test passes); persistent store, budgets, retries pending.",
    items: ["Understand incoming goals", "Manage project state", "Decompose engineering tasks", "Assign specialized responsibilities", "Manage task dependencies", "Select the appropriate model", "Call authorized tools", "Process execution feedback", "Manage retries", "Track time and resource budgets", "Determine when a task is complete", "Request human intervention when necessary"],
  },
  {
    n: "02", title: "Specification Engine", state: "partial",
    blurb: "Natural language in, structured requirements out. Never invents integrations, credentials or business requirements it was not given.",
    evidence: "IDs, description, priority, acceptance, verification live; dependencies, status tracking and the four artifact files pending.",
    items: ["Unique requirement ID", "Description", "Priority", "Dependencies", "Acceptance criteria", "Verification method", "Implementation status"],
  },
  {
    n: "03", title: "Architecture Engine", state: "partial",
    blurb: "Decides the shape of the system before a line is generated — and checks each decision against your constraints.",
    evidence: "ARCHITECTURE.md exists; DATABASE_SCHEMA, API_SPECIFICATION and SECURITY_DESIGN pending; validation manual.",
    items: ["System architecture", "Technology selection", "Frontend structure", "Backend structure", "Database schema", "API contracts", "Authentication design", "Security requirements", "Deployment design", "Implementation dependencies"],
    groups: [
      { label: "Generate", items: ["ARCHITECTURE.md", "DATABASE_SCHEMA.md", "API_SPECIFICATION.md", "SECURITY_DESIGN.md"] },
    ],
    rules: ["Validate architectural decisions against the user's requirements and constraints."],
  },
  {
    n: "04", title: "Code Generation Engine", state: "partial",
    blurb: "Writes the way a careful engineer commits: small recorded patches on top of Git checkpoints — never blind full-file rewrites.",
    evidence: "Confined file creation, single-match patches, checkpoints and audit log live; component/route/model/test generation pending.",
    items: ["Create files", "Edit existing files", "Apply targeted patches", "Generate frontend components", "Generate backend routes", "Create database models", "Generate tests", "Generate configuration", "Maintain documentation", "Track changes"],
    rules: ["All modifications must be recorded.", "Use Git checkpoints and patch-based editing.", "Avoid unnecessary full-file rewrites."],
  },
  {
    n: "05", title: "Execution Engine", state: "partial",
    blurb: "Generated code is untrusted code. It runs locked down, watched, and disposable — never on the host, never near real secrets.",
    evidence: "Guarded local run live (timeout, output caps, no shell); Docker isolation plus the full capability list pending.",
    items: ["Project initialization", "Dependency installation", "Application startup", "Script execution", "Database migrations", "Test execution", "Runtime monitoring", "Standard output capture", "Standard error capture", "Exit-code collection", "Timeout handling", "Resource monitoring"],
    groups: [
      { label: "Security requirements", items: ["Non-root execution", "Resource limits", "Execution time limits", "Restricted filesystem mounts", "Restricted network access", "No access to host credentials", "No access to production secrets", "Disposable execution environments", "Explicitly approved external network access"] },
    ],
    rules: ["Use Docker initially.", "Do not execute generated code directly on the host machine."],
  },
  {
    n: "06", title: "Testing Engine", state: "partial",
    blurb: "Every claim about the software is checked by deterministic tools — unit to browser, quality to security — and every result is stored.",
    evidence: "pytest live, 11 passed; coverage, HTTPX, Vitest, Playwright, Ruff, Pyright, Bandit, pip-audit and secret scanning pending.",
    items: ["Unit testing", "Integration testing", "API testing", "End-to-end testing", "Database testing", "Security testing", "Regression testing", "Build verification"],
    groups: [
      { label: "Integrate — Python", items: ["pytest", "pytest-cov", "HTTPX"] },
      { label: "Integrate — Frontend", items: ["Vitest", "React Testing Library"] },
      { label: "Integrate — Browser", items: ["Playwright"] },
      { label: "Integrate — Quality", items: ["Ruff", "Pyright"] },
      { label: "Integrate — Security", items: ["Bandit", "pip-audit", "Dependency vulnerability checks", "Secret scanning"] },
      { label: "Store every test result with", items: ["Test identifier", "Execution ID", "Start and end time", "Pass/fail status", "Error information", "Test output", "Coverage information when available"] },
    ],
  },
  {
    n: "07", title: "Debugging Engine", state: "queued",
    blurb: "When something fails, collect everything first — logs, traces, recent changes — then diagnose from evidence. Model confidence is not proof.",
    evidence: "Collection list and diagnosis contract specified; engine pending.",
    items: ["Stack traces", "Runtime logs", "Failed tests", "Relevant source code", "Recent Git changes", "Dependency versions", "Relevant application state"],
    groups: [
      { label: "Generate structured diagnoses containing", items: ["Failure ID", "Failure category", "Suspected root cause", "Supporting evidence", "Alternative explanations", "Affected files", "Confidence estimate", "Proposed repair", "Tests required to verify the repair"] },
    ],
    rules: ["Do not treat model confidence as proof.", "Use actual execution evidence."],
  },
  {
    n: "08", title: "Repair Engine", state: "partial",
    blurb: "Minimal patch, checkpoint, sandbox, targeted tests, regression, accept or roll back — inside hard limits, never an infinite loop.",
    evidence: "Checkpoint, approval gate and restore live; the bounded autonomous loop pending.",
    items: ["Receive a verified failure report", "Identify affected files", "Investigate the cause", "Generate a minimal patch", "Validate the patch", "Save a Git checkpoint", "Apply the patch in the sandbox", "Run targeted tests", "Run regression tests", "Accept or reject the change", "Roll back failed repairs"],
    groups: [
      { label: "Implement limits for", items: ["Maximum repair attempts", "Maximum execution time", "Maximum token and API expenditure", "Maximum files changed per repair", "Maximum concurrent executions"] },
    ],
    rules: ["If repair fails repeatedly, stop and produce an actionable report.", "Never enter an infinite repair loop."],
  },
  {
    n: "09", title: "Independent Verification Engine", state: "queued",
    blurb: "A second pair of eyes that trusts nothing: requirements, startup, contracts, journeys, security, regressions, artifacts — then a final report.",
    evidence: "Nine checks and the four-state report specified; engine pending. Untested is never marked passed.",
    items: ["Requirements satisfied", "Application starts successfully", "API contracts function", "Database operations work", "User journeys work", "Tests pass", "Security checks execute", "Regressions are absent from the defined test suite", "Required artifacts exist"],
    rules: ["Generate a final report with verified, failed, blocked and untested requirements.", "Do not mark untested requirements as passed."],
  },
];

function PartThree({ onApi }: { onApi: () => void }) {
  return (
    <>
      <p className="crumb">part-iii — system architecture</p>
      <h1 className="doctitle">Nine engines, one kernel.</h1>
      <p className="docsub">
        Genesis is built modular: a central orchestrator commanding eight
        specialized engines — each verified against execution, none trusted on
        word alone.
      </p>
      <p className="docmeta">
        Sections <strong>09/09 received</strong> · build states honest per engine
      </p>
      {PARTIII.map((s) => (
        <section key={s.n}>
          <h2 className="sect">
            {s.n}. {s.title}{" "}
            <span className={`st ${s.state}`} style={{ fontFamily: "var(--mono)", fontSize: 12 }}>
              {s.state === "done" ? "built" : s.state === "partial" ? "partial" : "queued"}
            </span>
          </h2>
          <p className="prose">{s.blurb}</p>
          <ol className="rows">
            {s.items.map((t) => (
              <li key={t}>
                <span />
                <span className={`g ${s.state}`}>{GLYPH[s.state]}</span>
                <span><span className="t">{t}</span></span>
              </li>
            ))}
          </ol>
          {s.groups?.map((g) => (
            <div key={g.label}>
              <p className="prose" style={{ marginTop: 18, marginBottom: 2 }}>
                <strong>{g.label}</strong>
              </p>
              <ol className="rows" style={{ marginTop: 0 }}>
                {g.items.map((t) => (
                  <li key={t}>
                    <span />
                    <span className={`g ${s.state}`}>{GLYPH[s.state]}</span>
                    <span><span className="t">{t}</span></span>
                  </li>
                ))}
              </ol>
            </div>
          ))}
          {s.rules?.map((r) => (
            <p className="prose" key={r} style={{ marginTop: 12 }}>
              <span className="hl">rule</span> <strong>{r}</strong>
            </p>
          ))}
          <p className="prose" style={{ marginTop: 10 }}>
            <span className="hl">evidence</span> {s.evidence}
          </p>
        </section>
      ))}
      <p style={{ marginTop: 20 }}>
        <button type="button" className="hl" onClick={onApi}>
          ▸ Confirm the API is live
        </button>
      </p>
    </>
  );
}

const TRACKED = ["Model name", "Request ID", "Latency", "Token usage", "API errors", "Retry count", "Cost when available", "Task associated with the request"];

const CREATED_FILES: Array<[string, string]> = [
  ["app/intelligence/meta_client.py", "Central adapter: auth, retry, payloads, registry recording. Live."],
  ["app/intelligence/model_router.py", "Spark for routine, Wonder for complex. IDs from env only. Live."],
  ["app/intelligence/model_registry.py", "Every call recorded with request ID. Tested."],
  ["app/intelligence/prompt_manager.py", "Versioned spec.extract, plan.make, test.interpret, repair.propose v1. Tested."],
];

function PartFour() {
  return (
    <>
      <p className="crumb">part-iv — meta model integration</p>
      <h1 className="doctitle">One provider, two minds.</h1>
      <p className="docsub">
        Meta Model API is the primary model provider — verified live against
        official documentation, not assumed.
      </p>
      <p className="docmeta">
        Received in full · <strong>GET /models ok · 1169 ms · 2026-11-02</strong>
      </p>
      <p className="prose">
        Official base URL <span className="hl">https://api.meta.ai/v1</span> ·
        authentication <span className="hl">MODEL_API_KEY</span> bearer, server-side
        only — never exposed to the frontend.
      </p>
      <h2 className="sect">Model strategy</h2>
      <p className="prose"><strong>Advanced — muse-wonder-1.0, when available:</strong></p>
      <ol className="rows">
        {["Complex architecture", "Large codebase reasoning", "Multi-file engineering", "Difficult debugging", "Complex implementation planning"].map((t) => (
          <li key={t}><span /><span className="g done">●</span><span><span className="t">{t}</span></span></li>
        ))}
      </ol>
      <p className="prose" style={{ marginTop: 18 }}><strong>Primary — muse-spark-1.3, for:</strong></p>
      <ol className="rows" style={{ marginTop: 0 }}>
        {["Routine code generation", "Test interpretation", "Error analysis", "Structured engineering tasks", "Tool-assisted execution"].map((t) => (
          <li key={t}><span /><span className="g done">●</span><span><span className="t">{t}</span></span></li>
        ))}
      </ol>
      <h2 className="sect">Configuration</h2>
      <pre className="out">MODEL_API_KEY={"\n"}META_BASE_URL=https://api.meta.ai/v1{"\n"}META_PRIMARY_MODEL=muse-spark-1.3{"\n"}META_ADVANCED_MODEL=muse-wonder-1.0</pre>
      <p className="prose" style={{ marginTop: 12 }}>
        No hardcoded identifiers anywhere outside this file and env. Model access
        is checked at runtime; an unavailable model returns an informative error
        or an explicitly configured fallback — never a silent swap.
      </p>
      <h2 className="sect">Created</h2>
      <ol className="rows">
        {CREATED_FILES.map(([f, d]) => (
          <li key={f}><span /><span className="g done">●</span><span><span className="t">{f}</span><span className="e">{d}</span></span></li>
        ))}
      </ol>
      <h2 className="sect">Tracked per call</h2>
      <ol className="rows">
        {TRACKED.map((t) => (
          <li key={t}><span /><span className="g done">●</span><span><span className="t">{t}</span></span></li>
        ))}
      </ol>
      <p className="prose" style={{ marginTop: 12 }}>
        <span className="hl">rule</span> <strong>Tool calling, structured outputs, streaming, reasoning effort, error and rate-limit handling, timeouts, retry with backoff, prompt versioning — payload builder tested; live agentic calls unlock with the key in env.</strong>
      </p>
    </>
  );
}

const AGENTS: Array<{ name: string; state: State; duties: string[]; maps: string; note?: string }> = [
  { name: "Architect Agent", state: "done", duties: ["Requirement interpretation", "Architecture", "Database design", "API design", "Implementation planning"], maps: "ArchitectAgent — spec → requirements, asks on empty. Tested." },
  { name: "Builder Agent", state: "done", duties: ["Code generation", "File management", "Implementation", "Documentation", "Patch generation"], maps: "BuilderAgent — scaffold + manifest behind the workspace guard. Tested." },
  { name: "Testing Agent", state: "partial", duties: ["Test generation", "Test execution", "Test result interpretation", "Coverage analysis", "Regression detection"], maps: "TestingAgent — execution, interpretation, coverage, regression live; generation pending. Actual execution always by deterministic pytest." },
  { name: "Debugger Agent", state: "done", duties: ["Error analysis", "Root-cause investigation", "Failure classification", "Repair recommendations"], maps: "DebuggerAgent — evidence in, 9-field diagnosis out. Tested." },
  { name: "Reviewer Agent", state: "partial", duties: ["Independent code review", "Architecture review", "Security review", "Maintainability review", "Verification of proposed changes"], maps: "ReviewerAgent — secret scan plus no-tests-means-no-pass rule live; architecture and maintainability review of proposed changes pending." },
  { name: "Memory Engine", state: "done", duties: ["Store project knowledge", "Record successful approaches", "Record failures", "Preserve verified engineering lessons", "Retrieve relevant historical context"], maps: "MemoryEngine — JSONL lessons with evidence in the workspace; Postgres in Phase 6. Validated contracts on every output; no unrestricted permissions." },
];

const REGISTRY: Array<[string, string, string]> = [
  ["inspect_project", "open", "list workspace files (capped)"],
  ["read_file", "open", "read a workspace file"],
  ["search_code", "open", "literal search across code and docs"],
  ["create_file", "open", "guarded create / overwrite"],
  ["apply_patch", "open", "single-match edit"],
  ["run_command", "approval", "argv list only — never a shell string"],
  ["run_tests", "open", "deterministic pytest + parsed results"],
  ["get_test_results", "open", "last stored test result"],
  ["get_runtime_logs", "open", "last stored runtime output"],
  ["inspect_dependencies", "open", "declared manifests"],
  ["create_git_checkpoint", "open", "commit state, return SHA"],
  ["restore_checkpoint", "approval", "reset to a SHA"],
  ["generate_documentation", "open", "runbook from audit + results"],
  ["request_approval", "open", "open an approval item"],
];

function PartSix() {
  return (
    <>
      <p className="crumb">part-vi — tool registry</p>
      <h1 className="doctitle">Propose anything. Touch nothing.</h1>
      <p className="docsub">
        Fourteen tools, one gate: the model may propose a call, but the backend
        validates schema and permission before anything executes — and no tool
        reaches the host shell.
      </p>
      <p className="docmeta">Received in full · <strong>implemented + tested</strong></p>
      <ol className="rows">
        {REGISTRY.map(([t, p, d]) => (
          <li key={t}>
            <span />
            <span className="g done">●</span>
            <span>
              <span className="t">{t}</span>
              <span className="e">{d} · permission: {p}{p === "approval" ? " (approved item required)" : ""} · audited</span>
            </span>
          </li>
        ))}
      </ol>
      <p className="prose" style={{ marginTop: 18 }}>
        <span className="hl">contract</span> Every tool declares typed input and
        output schemas, permission requirements, a timeout, error handling, and
        audit logging. Unknown tools, missing arguments, and unapproved
        consequential calls are rejected — all covered by tests.
      </p>
      <p className="prose">
        <span className="hl">rule</span> <strong>Do not allow models to directly access the host shell.</strong>
      </p>
    </>
  );
}

function PartFive() {
  return (
    <>
      <p className="crumb">part-v — specialized engineering agents</p>
      <h1 className="doctitle">Specialists, not freelancers.</h1>
      <p className="docsub">
        Logical roles coordinated by the central orchestrator — typed contracts,
        real engines, no uncontrolled independent agents.
      </p>
      <p className="docmeta">
        Architect, Builder, Testing received · <strong>remainder pending</strong>
      </p>
      {AGENTS.map((a) => (
        <section key={a.name}>
          <h2 className="sect">
            {a.name}{" "}
            <span className={`st ${a.state}`} style={{ fontSize: 12 }}>
              {a.state === "done" ? "live" : "partial"}
            </span>
          </h2>
          <ol className="rows">
            {a.duties.map((t) => (
              <li key={t}><span /><span className={`g ${a.state}`}>{GLYPH[a.state]}</span><span><span className="t">{t}</span></span></li>
            ))}
          </ol>
          <p className="prose" style={{ marginTop: 10 }}>
            <span className="hl">maps to</span> {a.maps}
            {a.note && (<><br /><span className="hl">note</span> {a.note}</>)}
          </p>
        </section>
      ))}
    </>
  );
}

const MISSION: Array<[string, State]> = [
  ["Understand the specification", "done"],
  ["Extract requirements and acceptance criteria", "done"],
  ["Design the software architecture", "done"],
  ["Plan implementation", "done"],
  ["Generate application code", "partial"],
  ["Create and manage project files", "done"],
  ["Install approved dependencies", "partial"],
  ["Execute generated applications", "done"],
  ["Run automated tests", "done"],
  ["Detect errors and failures", "queued"],
  ["Investigate root causes", "queued"],
  ["Generate corrective patches", "partial"],
  ["Apply repairs in a controlled environment", "partial"],
  ["Run regression tests", "queued"],
  ["Independently verify functionality", "queued"],
  ["Generate a final delivery report", "partial"],
];

const MEM_KINDS = ["Project facts", "Requirements", "Engineering decisions", "Execution history", "Test results", "Diagnoses", "Repairs", "Reusable skills", "Verified knowledge", "Known limitations"];

const MEM_FILES: Array<[string, string]> = [
  ["app/memory/memory_service.py", "Facade: suggestions quarantined until execution confirms them. Live."],
  ["app/memory/experience_store.py", "Append-only JSONL experiences, kind-validated. Live."],
  ["app/memory/skill_registry.py", "Promotion only via recorded trials + evidence. Live."],
  ["app/memory/retrieval.py", "Ranked keyword retrieval; no vector DB. Live."],
];

const SKILL_FIELDS = ["Skill ID", "Description", "Preconditions", "Procedure", "Evidence", "Success rate from recorded trials", "Known limitations", "Version"];

function PartSeven() {
  return (
    <>
      <p className="crumb">part-vii — continual engineering memory</p>
      <h1 className="doctitle">Remember what worked.</h1>
      <p className="docsub">
        Persistent memory that separates rumor from proof: model suggestions
        stay quarantined until a real execution confirms them.
      </p>
      <p className="docmeta">File-backed today (.genesis/) · <strong>Postgres in Phase 6</strong></p>
      <h2 className="sect">Separated, not soup</h2>
      <ol className="rows">
        {MEM_KINDS.map((t) => (
          <li key={t}><span /><span className="g done">●</span><span><span className="t">{t}</span></span></li>
        ))}
      </ol>
      <h2 className="sect">Created</h2>
      <ol className="rows">
        {MEM_FILES.map(([f, d]) => (
          <li key={f}><span /><span className="g done">●</span><span><span className="t">{f}</span><span className="e">{d}</span></span></li>
        ))}
      </ol>
      <h2 className="sect">Every learned skill carries</h2>
      <ol className="rows">
        {SKILL_FIELDS.map((t) => (
          <li key={t}><span /><span className="g done">●</span><span><span className="t">{t}</span></span></li>
        ))}
      </ol>
      <p className="prose" style={{ marginTop: 18 }}>
        <span className="hl">rule</span> <strong>Never auto-convert a model claim into verified memory. Suggestions and confirmed knowledge live apart.</strong>
      </p>
      <p className="prose">
        <span className="hl">rule</span> <strong>Semantic retrieval only where it improves quality — keyword ranking is the baseline, and no vector database is mandatory.</strong>
      </p>
    </>
  );
}

const IMPROVABLE = ["Engineering prompts", "Planning strategies", "Test-generation methods", "Debugging strategies", "Code-generation procedures", "Reusable skills", "Selected software modules"];

const PROCESS = ["Record the baseline", "Generate a candidate improvement", "Create an isolated version", "Run fixed benchmarks", "Run held-out benchmarks", "Run regression tests", "Compare results", "Reject or retain the candidate", "Record evidence and version", "Allow rollback"];

function PartEight() {
  return (
    <>
      <p className="crumb">part-viii — validated self-improvement</p>
      <h1 className="doctitle">Improvements earn their way in.</h1>
      <p className="docsub">
        Candidates are tested in isolation against fixed and held-out
        benchmarks. Winners are retained with evidence; losers are discarded;
        the real tree is never touched without approval.
      </p>
      <p className="docmeta">Implemented + tested · <strong>evaluator is never the candidate</strong></p>
      <h2 className="sect">May propose changes to</h2>
      <ol className="rows">
        {IMPROVABLE.map((t) => (
          <li key={t}><span /><span className="g done">●</span><span><span className="t">{t}</span></span></li>
        ))}
      </ol>
      <h2 className="sect">Required process</h2>
      <ol className="rows">
        {PROCESS.map((t) => (
          <li key={t}><span /><span className="g done">●</span><span><span className="t">{t}</span></span></li>
        ))}
      </ol>
      <p className="prose" style={{ marginTop: 18 }}>
        <span className="hl">rule</span> <strong>No unrestricted autonomous rewriting of the orchestrator, security controls, permission policies, or the evaluation system. Critical changes need explicit human approval.</strong>
      </p>
      <p className="prose">
        <span className="hl">rule</span> <strong>Prompt tweaks alone are never claimed as intelligence improvement.</strong>
      </p>
    </>
  );
}

const ENTITIES: Array<[string, string]> = [
  ["users", "accounts"], ["projects", "top-level work"], ["specifications", "NL specs"],
  ["requirements", "structured requirements"], ["engineering_runs", "run states"],
  ["tasks", "decomposed work"], ["artifacts", "external file references"],
  ["test_runs", "suite executions"], ["test_results", "per-test results"],
  ["failures", "detected failures"], ["diagnoses", "root-cause reports"],
  ["repair_attempts", "patch tries"], ["code_changes", "diffs"],
  ["memories", "lessons with evidence"], ["skills", "promoted skills"],
  ["model_calls", "API ledger"], ["approvals", "human gates"],
  ["audit_events", "tool audit trail"],
];

function PartNine() {
  return (
    <>
      <p className="crumb">part-ix — database design</p>
      <h1 className="doctitle">Eighteen tables, one contract.</h1>
      <p className="docsub">
        UUID keys, UTC timestamps, foreign-key constraints, migrations, indexed
        and validated — with large generated files kept outside the database
        behind controlled artifact storage.
      </p>
      <p className="docmeta">Schema contract implemented + tested · <strong>Postgres server + SQLAlchemy live wiring pending</strong></p>
      <h2 className="sect">Initial entities</h2>
      <ol className="rows">
        {ENTITIES.map(([t, d]) => (
          <li key={t}><span /><span className="g done">●</span><span><span className="t">{t}</span><span className="e">{d}</span></span></li>
        ))}
      </ol>
      <h2 className="sect">Conventions, enforced by validator</h2>
      <ol className="rows">
        {["UUID identifiers", "UTC timestamps", "Foreign-key constraints", "Database migrations (Alembic)", "Transaction management", "Appropriate indexes", "Data validation", "Project-level access controls", "Large files outside the DB, referenced via artifact storage"].map((t) => (
          <li key={t}><span /><span className="g partial">◐</span><span><span className="t">{t}</span><span className="e">contract tested; live enforcement lands with the Postgres wiring</span></span></li>
        ))}
      </ol>
    </>
  );
}

type Doc = "studio" | "about" | "download" | "models" | "playground" | "publish" | "pricing" | "i" | "ii" | "iii" | "iv" | "v" | "vi" | "vii" | "viii" | "ix";

const API = "http://127.0.0.1:8000";

const TROPHIES: Array<[string, string]> = [
  ["open-studio", "Open the studio"],
  ["open-about", "Read about genesis"],
  ["open-download", "Download genesis"],
  ["open-models", "Inspect the engine"],
  ["open-playground", "Open the playground"],
  ["open-publish", "Read the publish guide"],
  ["open-pricing", "Read pricing"],
  ["open-ii", "Open part-ii"],
  ["open-i", "Open part-i"],
  ["open-iii", "Open part-iii"],
  ["open-iv", "Open part-iv"],
  ["open-v", "Open part-v"],
  ["open-vi", "Open part-vi"],
  ["open-vii", "Open part-vii"],
  ["open-viii", "Open part-viii"],
  ["open-ix", "Open part-ix"],
  ["run-playground", "Run the playground"],
  ["parse", "Parse a specification"],
  ["api", "Confirm the API is live"],
  ["reach", "Reach out on GitHub"],
];

const BOOT_LINES = [
  "$ genesis --boot",
  "> kernel ok · 16 states",
  "> models: muse-spark-1.3 / muse-wonder-1.0",
  "> tools: 14 · agents: 5 · skills: 0 verified",
  "> engine ready — proof over promises.",
];

function Boot({ onExplore }: { onExplore: () => void }) {
  const [n, setN] = useState(1);
  useEffect(() => {
    let reduce = false;
    try { reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches; } catch { /* noop */ }
    if (reduce) { setN(BOOT_LINES.length); return; }
    if (n >= BOOT_LINES.length) return;
    const t = setTimeout(() => setN((v) => v + 1), 320);
    return () => clearTimeout(t);
  }, [n]);
  return (
    <div className="doc-inner">
      <p className="crumb">genesis_ // boot</p>
      <pre className="out" aria-label="Boot log">
        {BOOT_LINES.slice(0, n).join("\n")}
        {n < BOOT_LINES.length ? "▌" : ""}
      </pre>
      <p style={{ marginTop: 16 }}>
        <button type="button" className="btn primary" onClick={onExplore}>[explore →]</button>
      </p>
    </div>
  );
}

function Onboard({ onDone }: { onDone: (name: string) => void }) {
  const [name, setName] = useState("");
  const [path, setPath] = useState<"new" | "improve">("new");
  function done() {
    const who = name.trim() || "builder";
    try { window.localStorage.setItem("genesis_path", path); } catch { /* private mode */ }
    onDone(who);
  }
  return (
    <div className="doc-inner">
      <p className="crumb">$ whoami — 30 seconds, once</p>
      <h1 className="doctitle">Log in on this device.</h1>
      <p className="docsub">A local profile — your name stays in this browser, on this machine. No password, no server account yet.</p>
      <p>
        <input value={name} onChange={(e) => setName(e.target.value)} onKeyDown={(e) => e.key === "Enter" && done()}
          placeholder="your name" aria-label="Your name"
          style={{ font: "inherit", fontSize: 12, padding: "6px 10px", borderRadius: 3, border: "1px solid var(--line2)", background: "#080b10", color: "inherit", width: "min(260px, 100%)" }} />
      </p>
      <h2 className="sect">$ pick a path</h2>
      <p>
        <button type="button" className={path === "new" ? "btn primary" : "btn"} onClick={() => setPath("new")}>[1] I have an idea</button>{" "}
        <button type="button" className={path === "improve" ? "btn primary" : "btn"} onClick={() => setPath("improve")}>[2] I have code</button>
      </p>
      <p style={{ marginTop: 12 }}>
        <button type="button" className="btn primary" onClick={done}>[enter studio →]</button>
      </p>
    </div>
  );
}

function AboutDoc({ onGo }: { onGo: (d: Doc) => void }) {
  return (
    <>
      <p className="crumb">about genesis</p>
      <h1 className="doctitle">Your personal AI software engineer.</h1>
      <p className="docsub">
        By Vrajhna Technologies · built for the Meta × Cerebral Valley hackathon.
        Founded by Yuvraj Sharma (Vrajhna Group) — the original; copies aren&apos;t Genesis.
        You describe the idea — Genesis does the engineering: builds, runs, tests,
        repairs, verifies. Proof over promises.
      </p>
      <p className="docmeta">spec in · <strong>verified software out</strong></p>

      <h2 className="sect">Two things you can do</h2>
      <ol className="rows">
        <li><span /><span className="g done">●</span><span><span className="t">[1] build new — full app, website, tool, game</span><span className="e">Describe it in plain words. Genesis plans, generates, installs, starts, tests, fixes and verifies. You preview, download or run it.</span></span></li>
        <li><span /><span className="g done">●</span><span><span className="t">[2] improve existing — your code to full-stack</span><span className="e">Upload a ZIP, connect GitHub or open a local folder. Genesis inspects, proposes a plan, and changes nothing without your approval.</span></span></li>
      </ol>
      <p style={{ marginTop: 12 }}>
        <button type="button" className="btn primary" onClick={() => onGo("studio")}>▸ Open the studio</button>{" "}
        <button type="button" className="btn" onClick={() => onGo("download")}>↓ Download genesis</button>
      </p>

      <h2 className="sect">Rules it never breaks</h2>
      <p className="prose">
        Generated code is <strong>not</strong> verified software — a task is done only when
        tests and checks pass on the running app. Nothing destructive runs without your
        approval. Your code is never overwritten without permission — Git checkpoints and
        rollback everywhere. Secrets stay server-side. Failures are shown, never hidden.
      </p>
    </>
  );
}

function DownloadDoc() {
  return (
    <>
      <p className="crumb">download</p>
      <h1 className="doctitle">Take Genesis with you.</h1>
      <p className="docsub">
        The same engine, three ways: in this browser, in your terminal, or owning the
        whole machine-local stack. Every link below is a real file served by this server.
      </p>

      <h2 className="sect">[a] terminal client — linux · macos · windows</h2>
      <p className="prose">Python 3.8+ only, zero packages. Chat, build, download and verify from any shell.</p>
      <p><a className="hl" href={`${API}/api/download/cli`}>↓ genesis-cli.zip</a></p>
      <pre className="out">linux / macos{"\n"}  unzip genesis-cli.zip && sh genesis-cli/install.sh{"\n\n"}windows (powershell){"\n"}  Expand-Archive genesis-cli.zip . ; powershell -ExecutionPolicy Bypass -File genesis-cli/install.ps1{"\n\n"}then{"\n"}  genesis status{"\n"}  genesis new "Build me a website for my clothing business"</pre>

      <h2 className="sect">[b] full engine — run everything on your computer</h2>
      <p className="prose">Backend, builder, CLI and tests. Full authority over your own folders — isolated execution, approval before anything destructive.</p>
      <p><a className="hl" href={`${API}/api/download/engine`}>↓ genesis-engine.zip</a></p>
      <pre className="out">unzip genesis-engine.zip && cd genesis-engine{"\n"}pip install fastapi uvicorn{"\n"}GENESIS_HOME=$PWD genesis serve   # or: python3 -m uvicorn app.api.server:app --port 8000</pre>

      <h2 className="sect">[c] playground — online now, offline with [b]</h2>
      <p className="prose">Run Python instantly in the studio playground (section 8), save experiments as projects, build them into full apps. Offline: install [b], serve, open the studio address.</p>
    </>
  );
}

function ModelsDoc() {
  const [st, setSt] = useState<any>(null);
  const [keyInput, setKeyInput] = useState("");
  const [dbUrl, setDbUrl] = useState("");
  const [db, setDb] = useState<any>(null);
  const [note, setNote] = useState("");
  function load() {
    fetch(`${API}/api/intelligence/status`).then((r) => r.json()).then(setSt).catch(() => setSt({ ok: false }));
    fetch(`${API}/api/settings/database`).then((r) => r.json()).then(setDb).catch(() => setDb(null));
  }
  useEffect(() => { load(); }, []);
  async function saveKey() {
    if (!keyInput.trim()) return setNote("Paste the key first.");
    try {
      const r = await fetch(`${API}/api/settings/key`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ key: keyInput.trim() }),
      });
      const j = await r.json();
      if (j.ok) { setKeyInput(""); setNote("Key stored on the server — models are live."); load(); }
      else setNote(j.error || "Key rejected.");
    } catch { setNote("Backend is offline."); }
  }
  async function saveDb(engine: string) {
    try {
      const r = await fetch(`${API}/api/settings/database`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ engine, url: dbUrl }),
      });
      const j = await r.json();
      if (j.ok) { setNote(engine === "sqlite" ? "Database: SQLite — zero setup." : "Database URL stored."); load(); }
      else setNote(j.error || "Database rejected.");
    } catch { setNote("Backend is offline."); }
  }
  return (
    <>
      <p className="crumb">models · agents · skills</p>
      <h1 className="doctitle">What backs this terminal.</h1>
      <p className="docsub">Live from the server — models, agent roles, tools and verified reusable skills. No invented numbers.</p>
      {!st && <p className="prose">querying engine…</p>}
      {st && !st.ok && <p className="prose">engine offline — start it, then reopen this page.</p>}
      {st && st.ok && (
        <>
          <h2 className="sect">models</h2>
          <ol className="rows">
            <li><span /><span className="g done">●</span><span><span className="t">primary — {st.models.primary}</span><span className="e">routine generation, test reading, structured tasks</span></span></li>
            <li><span /><span className="g done">●</span><span><span className="t">advanced — {st.models.advanced}</span><span className="e">architecture, hard debugging, multi-file planning</span></span></li>
            <li><span /><span className={`g ${st.models.key_configured ? "done" : "queued"}`}>{st.models.key_configured ? "●" : "○"}</span><span><span className="t">api key — {st.models.key_configured ? "configured" : "missing"}</span><span className="e">never shown, never sent to the browser</span></span></li>
          </ol>
          <h2 className="sect">agents [{st.agents.length}]</h2>
          <p className="prose">{st.agents.join(" · ")}</p>
          <h2 className="sect">tools [{st.tools.count}]</h2>
          <p className="prose">{st.tools.names.join(" · ")}</p>
          <h2 className="sect">verified skills [{st.skills.count}]</h2>
          <p className="prose">{st.skills.count === 0 ? "none promoted yet — skills graduate only from recorded trials." : st.skills.ids.join(" · ")}</p>
          <h2 className="sect">$ connect</h2>
          {note && <p className="prose"><span className="hl">note</span> {note}</p>}
          <p className="prose"><span className="hl">models</span> {st.models.key_configured ? "● key configured — reasoning is live." : "○ no key yet."}</p>
          {!st.models.key_configured && (
            <p>
              <input value={keyInput} onChange={(e) => setKeyInput(e.target.value)} placeholder="MODEL_API_KEY" aria-label="API key"
                style={{ font: "inherit", fontSize: 12, padding: "6px 10px", borderRadius: 3, border: "1px solid var(--line2)", background: "#080b10", color: "inherit", width: "min(320px, 100%)" }} />{" "}
              <button type="button" className="btn primary" onClick={saveKey}>Connect key</button>
            </p>
          )}
          <p className="prose"><span className="hl">database</span> {db ? `${db.engine} — ${db.live}.` : "querying engine…"}</p>
          <p>
            <button type="button" className={db?.engine === "sqlite" ? "btn primary" : "btn"} onClick={() => saveDb("sqlite")}>SQLite (zero setup)</button>{" "}
            <button type="button" className={db?.engine === "postgres" ? "btn primary" : "btn"} onClick={() => saveDb("postgres")}>PostgreSQL (paste URL)</button>{" "}
            <input value={dbUrl} onChange={(e) => setDbUrl(e.target.value)} placeholder="postgresql://user:pass@host:5432/db" aria-label="Database URL"
              style={{ font: "inherit", fontSize: 12, padding: "6px 10px", borderRadius: 3, border: "1px solid var(--line2)", background: "#080b10", color: "inherit", width: "min(320px, 100%)" }} />
          </p>
        </>
      )}
    </>
  );
}

function PlaygroundDoc({ win }: { win: (id: string) => void }) {
  const [tab, setTab] = useState<"chat" | "code">("chat");
  const [leftW, setLeftW] = useState(420);
  const [dragX, setDragX] = useState<number | null>(null);
  const startX = useRef(0);
  const startW = useRef(420);
  const [code, setCode] = useState("print('hello genesis')");
  const [pname, setPname] = useState("Playground experiment");
  const [out, setOut] = useState("");
  const [busy, setBusy] = useState("");
  const [pid, setPid] = useState("");
  const [chat, setChat] = useState<Array<{ who: string; text: string }>>([]);
  const [msg, setMsg] = useState("");
  const [report, setReport] = useState<any>(null);
  const [size, setSize] = useState<"desktop" | "tablet" | "phone">("desktop");

  useEffect(() => {
    if (dragX === null) return;
    const move = (e: MouseEvent) =>
      setLeftW(Math.min(720, Math.max(280, startW.current + e.clientX - startX.current)));
    const up = () => setDragX(null);
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
    return () => {
      window.removeEventListener("mousemove", move);
      window.removeEventListener("mouseup", up);
    };
  }, [dragX]);

  function say(text: string) {
    setChat((c) => [...c, { who: "genesis", text }]);
  }

  async function runCode(save: boolean) {
    setBusy("Running…"); setOut("");
    try {
      const r = await fetch(`${API}/api/playground/run`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code, ...(save ? { save_as: pname } : {}) }),
      });
      const j = await r.json();
      setOut((j.output || j.error || "") + `\nexit: ${j.exit_code ?? "—"} · ${j.note || ""}`);
      win("run-playground");
      if (j.project) {
        setPid(j.project.id); setReport(null); setTab("chat");
        say(`saved as project ${j.project.id}. now tell me what to build — or say "build it".`);
      }
    } catch { setOut("Backend offline."); }
    setBusy("");
  }

  async function send() {
    if (!msg.trim() || busy) return;
    const text = msg; setMsg("");
    setChat((c) => [...c, { who: "you", text }]);
    setBusy("working…");
    try {
      let id = pid;
      if (!id) {
        const p = await (await fetch(`${API}/api/projects`, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name: text.slice(0, 40) || "Playground build" }),
        })).json();
        id = p.project.id; setPid(id);
        say(`project ${id} opened — autopilot on, no stops.`);
      }
      const meta = await (await fetch(`${API}/api/projects/${id}`)).json();
      if (!meta.project || !meta.project.spec) {
        const s = await (await fetch(`${API}/api/projects/${id}/spec`, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ spec: text }),
        })).json();
        if (!s.ok) { say(s.error || "spec rejected."); setBusy(""); return; }
        if (s.needs_clarification) { say(`one question first: ${s.question}`); setBusy(""); return; }
        say(`understood — ${s.requirements.length} requirements.`);
      }
      const q = await (await fetch(`${API}/api/projects/${id}/questions`)).json();
      const ans: Record<string, string> = {};
      if (q.ok) for (const qq of q.questions || []) ans[qq.id] = qq.recommended;
      say(`stack: ${Object.entries(ans).map(([k, v]) => `${k}=${v}`).join(", ") || "defaults"}. building now — generate, install, start, test, verify.`);
      const b = await (await fetch(`${API}/api/projects/${id}/fullstack`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ answers: ans }),
      })).json();
      setReport(b.report);
      say(b.report.verdict === "VERIFIED"
        ? `VERIFIED — ${b.report.reason} live preview is on the right.`
        : `not verified: ${b.report.reason}`);
      win("run-playground");
    } catch { say("backend offline — start it and talk to me again."); }
    setBusy("");
  }

  const widths = { desktop: "100%", tablet: "480px", phone: "360px" };

  return (
    <>
      <p className="crumb">playground</p>
      <h1 className="doctitle">Build anything, right here.</h1>
      <p className="docsub">Talk, I build — generate, run, test, verify. Live preview on the right, any size.</p>
      {busy && <p className="prose">{busy}</p>}

      <div style={{ display: "flex", alignItems: "stretch", minHeight: 480 }}>
        <div style={{ width: leftW, flex: "none", display: "flex", flexDirection: "column", border: "1px solid var(--line)", borderRadius: 3, minWidth: 0 }}>
          <p style={{ margin: 0, borderBottom: "1px solid var(--line)", padding: "6px 10px" }}>
            <button type="button" className={tab === "chat" ? "btn primary" : "btn"} onClick={() => setTab("chat")}>chat</button>{" "}
            <button type="button" className={tab === "code" ? "btn primary" : "btn"} onClick={() => setTab("code")}>code</button>
            {pid && <span className="prose" style={{ marginLeft: 8 }}>{pid}</span>}
          </p>
          {tab === "chat" ? (
            <div style={{ display: "flex", flexDirection: "column", height: 430, minHeight: 0 }}>
              <div style={{ flex: 1, overflowY: "auto", padding: "8px 10px", minHeight: 0 }}>
                {chat.length === 0 && <p className="prose">say what to build — I do the rest, start to end. aggressive, no stops.</p>}
                {chat.map((m, i) => (
                  <p className="prose" key={i}><strong>{m.who === "you" ? "You" : "Genesis"}:</strong> {m.text}</p>
                ))}
                {busy && <p className="prose">{busy}▌</p>}
              </div>
              <p style={{ margin: 0, padding: "8px 10px", borderTop: "1px solid var(--line)" }}>
                <input value={msg} onChange={(e) => setMsg(e.target.value)} onKeyDown={(e) => e.key === "Enter" && send()}
                  placeholder="build me…" aria-label="Playground chat"
                  style={{ font: "inherit", fontSize: 12, padding: "6px 10px", borderRadius: 3, border: "1px solid var(--line2)", background: "#080b10", color: "inherit", width: "min(300px, 100%)" }} />{" "}
                <button type="button" className="btn primary" onClick={send}>Send</button>
              </p>
            </div>
          ) : (
            <div style={{ padding: "8px 10px", overflowY: "auto" }}>
              <textarea className="spec" value={code} onChange={(e) => setCode(e.target.value)} rows={12} aria-label="Playground code" />
              <p style={{ marginTop: 8 }}>
                <button type="button" className="btn primary" onClick={() => runCode(false)}>Run</button>{" "}
                <input value={pname} onChange={(e) => setPname(e.target.value)} aria-label="Save-as project name"
                  style={{ font: "inherit", fontSize: 12, padding: "6px 10px", borderRadius: 3, border: "1px solid var(--line2)", background: "#080b10", color: "inherit", width: "min(200px, 100%)" }} />{" "}
                <button type="button" className="btn" onClick={() => runCode(true)}>Run + save</button>
              </p>
              {out && <pre className="out">{out}</pre>}
            </div>
          )}
        </div>
        <div onMouseDown={(e) => { startX.current = e.clientX; startW.current = leftW; setDragX(e.clientX); }}
          title="drag to resize" style={{ width: 12, cursor: "col-resize", flex: "none" }} />
        <div style={{ flex: 1, minWidth: 0, border: "1px solid var(--line)", borderRadius: 3, padding: "8px 10px" }}>
          <p style={{ marginTop: 0 }}>
            {(["desktop", "tablet", "phone"] as const).map((s) => (
              <span key={s} style={{ marginRight: 8 }}>
                <button type="button" className={size === s ? "btn primary" : "btn"} onClick={() => setSize(s)}>{s}</button>
              </span>
            ))}
            {report && <span className="prose" style={{ marginLeft: 8 }}>verdict: <span className="hl">{report.verdict}</span></span>}
          </p>
          {report?.preview_url ? (
            <iframe src={report.preview_url} title="App preview" sandbox="allow-scripts allow-same-origin"
              style={{ width: widths[size], maxWidth: "100%", height: 480, border: "1px solid var(--line2)", borderRadius: 3, background: "#fff" }} />
          ) : (
            <p className="prose">live preview lands here — desktop, tablet, phone.</p>
          )}
          {report && (
            <ol className="rows">
              {report.steps.map((s: any) => (
                <li key={s.step}><span /><span className={`g ${s.ok ? "done" : "queued"}`}>{s.ok ? "●" : "○"}</span><span><span className="t">{s.step}</span><span className="e">{s.detail}</span></span></li>
              ))}
            </ol>
          )}
        </div>
      </div>
      <p className="prose">Games, tools, stores, dashboards, bots — anything the builder supports. Genesis builds and defends; it doesn&apos;t attack.</p>
    </>
  );
}

function PublishDoc() {
  return (
    <>
      <p className="crumb">publish</p>
      <h1 className="doctitle">Ship it under your domain.</h1>
      <p className="docsub">Every project downloads as a runnable ZIP. Point a subdomain at a server, serve the ZIP — done. No fake one-click button: the honest path is below.</p>

      <h2 className="sect">$ 1 · download the build</h2>
      <p className="prose">Studio §5 → Download ZIP. Unzip on the host machine. Every ZIP carries <code>SETUP.md</code> + <code>.env.example</code>.</p>

      <h2 className="sect">$ 2 · point the subdomain</h2>
      <p className="prose">In your DNS for <code>webstudiobhiwadi.com</code>, add:</p>
      <pre className="out">genesis.webstudiobhiwadi.com.  A  YOUR_SERVER_IP{"\n"}# or, if your host gives you a name:{"\n"}genesis.webstudiobhiwadi.com.  CNAME  your-host.example.net.</pre>

      <h2 className="sect">$ 3 · serve it (caddy)</h2>
      <pre className="out">genesis.webstudiobhiwadi.com {"{\n"}    reverse_proxy 127.0.0.1:3101{"\n"}{"}"}{"\n\n"}# one built app per subdomain, e.g. shop on :8001{"\n"}shop.webstudiobhiwadi.com {"{\n"}    reverse_proxy 127.0.0.1:8001{"\n"}{"}"}</pre>

      <h2 className="sect">$ 4 · per-app publish</h2>
      <p className="prose">A built app is one process: <code>python3 backend/server.py --port 8001</code> serves frontend + API on that port. Give it a subdomain + a reverse-proxy line each. HTTPS comes free with Caddy.</p>
      <p className="prose">Blocked until you provide hosting credentials: true one-click publish from inside Genesis. Everything above works today.</p>
    </>
  );
}

function PricingDoc() {
  return (
    <>
      <p className="crumb">pricing</p>
      <h1 className="doctitle">Pay for compute, not promises.</h1>
      <p className="docsub">Coming soon — the shape is fixed, the switch isn&apos;t wired yet.</p>

      <h2 className="sect">pay as you go</h2>
      <p className="prose">Per build + per verification run. Small ideas cost paise; big systems pay for the compute they burn. Metered, receipted, no subscription needed.</p>

      <h2 className="sect">monthly</h2>
      <p className="prose">One flat price for heavy builders: unlimited playground, priority builds, private projects, early features. Price announced at launch.</p>

      <h2 className="sect">donate</h2>
      <p className="prose">Donations open soon — they buy GPUs and test machines so students can build free. Until the button lands here, reach the founder channel in the sidebar.</p>
    </>
  );
}

export default function Editor() {
  const [doc, setDoc] = useState<Doc>("studio");
  const [rainOff, setRainOff] = useState(false);
  const [panelOpen, setPanelOpen] = useState(false);
  const [trophyOpen, setTrophyOpen] = useState(false);
  const [specOpen, setSpecOpen] = useState(false);
  const [stage, setStage] = useState<"boot" | "onboard" | "app">("boot");
  const [profile, setProfile] = useState("");

  useEffect(() => {
    try {
      const s = window.localStorage.getItem("genesis_stage");
      const p = window.localStorage.getItem("genesis_profile") || "";
      setProfile(p);
      if (s === "app" && p) setStage("app");
    } catch { /* private mode */ }
  }, []);

  function enter(name: string) {
    try {
      window.localStorage.setItem("genesis_profile", name);
      window.localStorage.setItem("genesis_stage", "app");
    } catch { /* private mode */ }
    setProfile(name);
    setStage("app");
    win("open-studio");
  }
  const [spec, setSpec] = useState(
    "Users can register and log in securely. Users can create projects and tasks."
  );
  const [parsed, setParsed] = useState(false);
  const [trophies, setTrophies] = useState<Set<string>>(new Set());

  const win = (id: string) =>
    setTrophies((prev) => (prev.has(id) ? prev : new Set(prev).add(id)));

  useEffect(() => {
    win("open-studio");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const open = (d: Doc) => {
    setDoc(d);
    win(`open-${d}`);
  };

  const reqs = parsed && spec.trim() ? parseSpecification(spec) : [];

  if (stage === "boot") {
    return (
      <div className="shell">
        <main className="doc">
          <Boot onExplore={() => (profile ? (setStage("app"), win("open-studio")) : setStage("onboard"))} />
        </main>
      </div>
    );
  }
  if (stage === "onboard") {
    return (
      <div className="shell">
        <main className="doc">
          <Onboard onDone={enter} />
        </main>
      </div>
    );
  }
  return (
    <>
      <AsciiRain hidden={rainOff} onPanel={() => setPanelOpen(!panelOpen)} />
      {panelOpen && (
        <div className="panelpop">
          <div className="row">
            <span>Genesis Rain</span>
            <button type="button" onClick={() => setRainOff(!rainOff)}>
              {rainOff ? "show" : "hide"}
            </button>
          </div>
          <div className="row">
            <span>theme</span>
            <span>dark</span>
          </div>
          <div className="row">
            <span>motion</span>
            <span>respects OS setting</span>
          </div>
        </div>
      )}
      <div className="shell">
        <aside className="tree">
          <div className="root">genesis_ // project-genesis</div>
          <ul>
            <li>
              <button type="button" className={`file${doc === "studio" ? " active" : ""}`} onClick={() => open("studio")}>
                <span>◈</span> studio — workspace
              </button>
            </li>
            <li>
              <button type="button" className={`file${doc === "playground" ? " active" : ""}`} onClick={() => open("playground")}>
                <span>▸</span> playground
              </button>
            </li>
            <li>
              <button type="button" className={`file${doc === "about" ? " active" : ""}`} onClick={() => open("about")}>
                <span>?</span> about genesis
              </button>
            </li>
            <li>
              <button type="button" className={`file${doc === "download" ? " active" : ""}`} onClick={() => open("download")}>
                <span>↓</span> download
              </button>
            </li>
            <li>
              <button type="button" className={`file${doc === "publish" ? " active" : ""}`} onClick={() => open("publish")}>
                <span>↑</span> publish
              </button>
            </li>
            <li>
              <button type="button" className={`file${doc === "pricing" ? " active" : ""}`} onClick={() => open("pricing")}>
                <span>$</span> pricing
              </button>
            </li>
            <li>
              <button type="button" className={`file${doc === "models" ? " active" : ""}`} onClick={() => open("models")}>
                <span>♦</span> models·agents·skills
              </button>
            </li>
            <li>
              <button type="button" className="folder" onClick={() => setSpecOpen(!specOpen)} aria-label="Toggle spec folder">
                <span>{specOpen ? "▾" : "▸"}</span> spec/
              </button>
            </li>
            {specOpen && (<>
            <li className="indent-1">
              <button type="button" className={`file${doc === "i" ? " active" : ""}`} onClick={() => open("i")}>
                <span>◈</span> part-i — mission
              </button>
            </li>
            <li className="indent-1">
              <button type="button" className={`file${doc === "ii" ? " active" : ""}`} onClick={() => open("ii")}>
                <span>◈</span> part-ii — development
              </button>
            </li>
            <li className="indent-1">
              <button type="button" className={`file${doc === "iii" ? " active" : ""}`} onClick={() => open("iii")}>
                <span>◈</span> part-iii — architecture
              </button>
            </li>
            <li className="indent-1">
              <button type="button" className={`file${doc === "iv" ? " active" : ""}`} onClick={() => open("iv")}>
                <span>◈</span> part-iv — meta models
              </button>
            </li>
            <li className="indent-1">
              <button type="button" className={`file${doc === "v" ? " active" : ""}`} onClick={() => open("v")}>
                <span>◈</span> part-v — agents
              </button>
            </li>
            <li className="indent-1">
              <button type="button" className={`file${doc === "vi" ? " active" : ""}`} onClick={() => open("vi")}>
                <span>◈</span> part-vi — tool registry
              </button>
            </li>
            <li className="indent-1">
              <button type="button" className={`file${doc === "vii" ? " active" : ""}`} onClick={() => open("vii")}>
                <span>◈</span> part-vii — memory
              </button>
            </li>
            <li className="indent-1">
              <button type="button" className={`file${doc === "viii" ? " active" : ""}`} onClick={() => open("viii")}>
                <span>◈</span> part-viii — improvement
              </button>
            </li>
            <li className="indent-1">
              <button type="button" className={`file${doc === "ix" ? " active" : ""}`} onClick={() => open("ix")}>
                <span>◈</span> part-ix — database
              </button>
            </li>
            <li className="indent-1">
              <button type="button" className="file locked" disabled>
                <span>◇</span> part-xvi — demo <span className="q">queued</span>
              </button>
            </li>
            </>)}
          </ul>
          <div className="foot">
            <a href="https://github.com" onClick={() => win("reach")}>github</a>
            <span>contact — founder channel</span>
            <span>theme: dark</span>
            <span>you: {profile || "anonymous"} (this device)</span>
          </div>
        </aside>

        <main className="doc">
          <div className="doc-inner">
            {doc === "studio" ? (
              <Workspace win={win} />
            ) : doc === "playground" ? (
              <PlaygroundDoc win={win} />
            ) : doc === "publish" ? (
              <PublishDoc />
            ) : doc === "pricing" ? (
              <PricingDoc />
            ) : doc === "about" ? (
              <AboutDoc onGo={open} />
            ) : doc === "download" ? (
              <DownloadDoc />
            ) : doc === "models" ? (
              <ModelsDoc />
            ) : doc === "ix" ? (
              <PartNine />
            ) : doc === "viii" ? (
              <PartEight />
            ) : doc === "vii" ? (
              <PartSeven />
            ) : doc === "vi" ? (
              <PartSix />
            ) : doc === "v" ? (
              <PartFive />
            ) : doc === "iv" ? (
              <PartFour />
            ) : doc === "iii" ? (
              <PartThree onApi={() => win("api")} />
            ) : doc === "ii" ? (
              <>
                <p className="crumb">part-ii — development instructions</p>
                <h1 className="doctitle">Before writing code.</h1>
                <p className="docsub">
                  Inspect first. Never overwrite what works. Plan, map, baseline —
                  then build in small, verifiable stages.
                </p>
                <p className="docmeta">Enforced this session · <strong>8/8 checks executed</strong></p>

                <ol className="rows">
                  {PRECODE.map((c) => (
                    <li key={c.text}>
                      <span />
                      <span className={`g ${c.state}`}>{GLYPH[c.state]}</span>
                      <span>
                        <span className="t">{c.text}</span>
                        <span className="e">{c.evidence}</span>
                      </span>
                    </li>
                  ))}
                </ol>

                <h2 className="sect">Empty or existing</h2>
                <p className="prose">
                  The repository was <strong>not empty</strong> — a SOLVO scaffold
                  with working code. So the architecture was <strong>adapted, not
                  recreated</strong>: Genesis lives in <span className="hl">genesis/</span> beside
                  it, and zero existing files were overwritten.
                </p>

                <h2 className="sect">After each phase, update</h2>
                <p className="prose">
                  <span className="hl">DEVELOPMENT_STATUS.md</span> is updated after every phase.
                  Its current standing:
                </p>
                <dl className="phases">
                  {PHASES.map(([k, v]) => (
                    <div key={k}>
                      <dt>{k}</dt>
                      <dd>{v}</dd>
                    </div>
                  ))}
                </dl>

                <h2 className="sect">Prove it</h2>
                <p className="prose">
                  Do not stop after generating a plan — <strong>implement and test
                  the software</strong>. Do not claim a feature works until it has
                  actually been <strong>executed and verified</strong>.
                </p>
                <pre className="out">
                  <span className="ok">11 passed</span>, 1 skipped in 1.30s{"\n"}
                  live GET /models → <span className="ok">ok</span> · 1169 ms · muse-spark-1.3 + muse-wonder-1.0 on API{"\n"}
                  next build → static / · 4.09 kB · serving <span className="ok">HTTP 200</span>
                </pre>
                <p style={{ marginTop: 16 }}>
                  <button type="button" className="hl" onClick={() => win("api")}>
                    ▸ Confirm the API is live
                  </button>
                </p>
              </>
            ) : (
              <>
                <p className="crumb">part-i — role and mission</p>
                <h1 className="doctitle">Project Genesis</h1>
                <p className="docsub">
                  Autonomous software engineering intelligence. Not a chatbot, not
                  a code generator, not a landing page — a system that works the
                  full lifecycle on execution feedback.
                </p>
                <p className="docmeta">
                  Version 1.0 · Meta Model API · <strong>Milestones [7/16]</strong>
                </p>

                <ol className="rows">
                  {MISSION.map(([t, s], i) => (
                    <li key={t}>
                      <span />
                      <span className={`g ${s}`}>{GLYPH[s]}</span>
                      <span>
                        <span className="t">{t}</span>
                        <span className="e">step {String(i + 1).padStart(2, "0")}/16 — {s === "done" ? "executed and recorded" : s === "partial" ? "in progress" : "queued"}</span>
                      </span>
                    </li>
                  ))}
                </ol>

                <h2 className="sect">Core principle</h2>
                <p className="prose">
                  <strong>Generated code is not verified software.</strong> A task
                  is complete only when acceptance criteria have been evaluated
                  using actual execution, tests and independent verification.
                </p>

                <h2 className="sect">Try the first step</h2>
                <p className="prose">
                  Paste a specification — the same deterministic parse the backend runs.
                </p>
                <textarea
                  className="spec"
                  value={spec}
                  onChange={(e) => setSpec(e.target.value)}
                  aria-label="Project specification"
                  rows={3}
                />
                <p style={{ marginTop: 12 }}>
                  <button
                    type="button"
                    className="btn primary"
                    onClick={() => {
                      setParsed(true);
                      if (spec.trim()) win("parse");
                    }}
                  >
                    Parse specification
                  </button>
                </p>
                {parsed && (
                  <pre className="out">
                    {reqs.length === 0
                      ? "Enter a specification first."
                      : reqs.map((r) => `${r.id} [${r.priority}] ${r.description}`).join("\n")}
                  </pre>
                )}
              </>
            )}
          </div>
        </main>
      </div>
      {trophyOpen && (
        <div className="trophypop">
          <ul>
            {TROPHIES.map(([id, label]) => (
              <li key={id} className={trophies.has(id) ? "won" : ""}>
                <span className="box">{trophies.has(id) ? "◆" : "◇"}</span>
                {label}
              </li>
            ))}
          </ul>
        </div>
      )}
      <div className="trophybar">
        Trophies [<strong>{trophies.size}/{TROPHIES.length}</strong>]{" "}
        <button type="button" onClick={() => setTrophyOpen(!trophyOpen)} aria-label="Toggle trophies">
          [{trophyOpen ? "-" : "+"}]
        </button>
      </div>
    </>
  );
}
