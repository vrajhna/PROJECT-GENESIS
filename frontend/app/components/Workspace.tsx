"use client";

import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_GENESIS_API || "http://127.0.0.1:8000";

interface Step {
  step: string;
  ok: boolean;
  detail: string;
  evidence: string;
}

interface Report {
  verdict: string;
  reason: string;
  steps: Step[];
  preview_url?: string;
  test_output?: string;
  diagnosis?: Record<string, unknown>;
  decisions?: Array<{ decision: string; reason: string }>;
}

export default function Workspace({ win }: { win: (id: string) => void }) {
  const [online, setOnline] = useState<boolean | null>(null);
  const [pid, setPid] = useState("");
  const [pname, setPname] = useState("My clothing website");
  const [spec, setSpec] = useState(
    "Build me a website for my clothing business with a home page, product list and contact section."
  );
  const [reqs, setReqs] = useState<Array<{ id: string; description: string; priority: string }>>([]);
  const [chat, setChat] = useState<Array<{ who: string; text: string }>>([]);
  const [msg, setMsg] = useState("");
  const [report, setReport] = useState<Report | null>(null);
  const [busy, setBusy] = useState("");
  const [notice, setNotice] = useState("");
  const [files, setFiles] = useState<string[]>([]);
  const [sel, setSel] = useState("");
  const [code, setCode] = useState("");
  const [ghUrl, setGhUrl] = useState("");
  const [ghMsg, setGhMsg] = useState("");
  const [localFiles, setLocalFiles] = useState<string[]>([]);
  const [dash, setDash] = useState<any>(null);
  const [playCode, setPlayCode] = useState("print('hello genesis')");
  const [playName, setPlayName] = useState("Playground experiment");
  const [playOut, setPlayOut] = useState("");
  const [termCmd, setTermCmd] = useState("echo hello");
  const [termReq, setTermReq] = useState<any>(null);
  const [termOut, setTermOut] = useState("");
  const [sugs, setSugs] = useState<any[]>([]);
  const [mode, setMode] = useState<"new" | "improve">(() => {
    try {
      return window.localStorage.getItem("genesis_path") === "improve" ? "improve" : "new";
    } catch {
      return "new";
    }
  });
  const [auto, setAuto] = useState<boolean | null>(null);

  async function flipAuto(v: boolean) {
    if (!pid) return setNotice("Create a project first.");
    try {
      const r = await fetch(`${API}/api/projects/${pid}/policy`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ autopilot: v }),
      });
      const j = await r.json();
      setAuto(j.policy.autopilot);
      setNotice(j.policy.autopilot ? "Autopilot on — safe steps run at once. Push, deploy, payments and secrets still ask." : "Autopilot off — every step asks first.");
    } catch {
      setNotice("Backend is offline.");
    }
  }
  const [questions, setQuestions] = useState<any[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});

  async function fetchQuestions() {
    if (!pid) return;
    try {
      const r = await fetch(`${API}/api/projects/${pid}/questions`);
      const j = await r.json();
      if (j.ok) {
        setQuestions(j.questions || []);
        const defaults: Record<string, string> = {};
        for (const q of j.questions || []) defaults[q.id] = q.recommended;
        setAnswers(defaults);
      }
    } catch {
      /* offline */
    }
  }

  async function check() {
    try {
      const r = await fetch(`${API}/api/health`);
      setOnline(r.ok);
    } catch {
      setOnline(false);
    }
  }

  useEffect(() => {
    check();
  }, []);

  async function newProject() {
    setBusy("Creating project…");
    try {
      const r = await fetch(`${API}/api/projects`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: pname || "Untitled" }),
      });
      const j = await r.json();
      setPid(j.project.id);
      setReport(null);
      setReqs([]);
      setQuestions([]);
      setAnswers({});
      setAuto(true);
      setNotice(`Project ready: ${j.project.id}. Describe what to build, then press Build.`);
      win("open-studio");
    } catch {
      setNotice("Backend is offline. Start it first (see bottom of this page).");
    }
    setBusy("");
  }

  async function sendSpec() {
    if (!pid) return setNotice("Create a project first.");
    setBusy("Understanding…");
    try {
      const r = await fetch(`${API}/api/projects/${pid}/spec`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ spec }),
      });
      const j = await r.json();
      if (j.needs_clarification) {
        setChat((c) => [...c, { who: "genesis", text: j.question }]);
      } else {
        setReqs(j.requirements);
        setNotice(`${j.requirements.length} requirement(s) understood. Answer the stack choices, then press Build.`);
        fetchQuestions();
      }
    } catch {
      setNotice("Backend is offline.");
    }
    setBusy("");
  }

  async function sendChat() {
    if (!pid || !msg.trim()) return;
    const text = msg;
    setMsg("");
    setChat((c) => [...c, { who: "you", text }]);
    try {
      const r = await fetch(`${API}/api/projects/${pid}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text }),
      });
      const j = await r.json();
      setChat((c) => [...c, { who: "genesis", text: j.reply }]);
      if (j.requirements) setReqs(j.requirements);
    } catch {
      setChat((c) => [...c, { who: "genesis", text: "Backend is offline. Start it and try again." }]);
    }
  }

  async function build(kind: "build" | "fullstack") {
    if (!pid) return setNotice("Create a project first.");
    setBusy(kind === "fullstack"
      ? "Building full app — frontend, API, database, tests. Takes a few minutes…"
      : "Building — scaffold, install, start, test. This takes a minute…");
    setReport(null);
    try {
      const r = await fetch(`${API}/api/projects/${pid}/${kind}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: kind === "fullstack" ? JSON.stringify({ answers }) : "{}",
      });
      const j = await r.json();
      setReport(j.report);
      refreshTree();
      setNotice(j.report.verdict === "VERIFIED" ? "Verified. Preview, download, or run it locally." : `Not verified: ${j.report.reason}`);
    } catch {
      setNotice("Build request failed — is the backend still running?");
    }
    setBusy("");
  }

  async function refreshTree(id?: string) {
    const p = id || pid;
    if (!p) return;
    try {
      const r = await fetch(`${API}/api/projects/${p}/tree`);
      setFiles((await r.json()).files || []);
    } catch {
      /* offline */
    }
  }

  async function fetchDashboard() {
    try {
      setDash(await (await fetch(`${API}/api/dashboard`)).json());
    } catch {
      /* offline */
    }
  }

  useEffect(() => {
    fetchDashboard();
  }, [pid, report]);

  async function openProject(id: string) {
    setPid(id);
    setReport(null);
    setReqs([]);
    setQuestions([]);
    setAnswers({});
    setSel("");
    setCode("");
    setTermReq(null);
    setTermOut("");
    await refreshTree(id);
    try {
      const p = await (await fetch(`${API}/api/projects/${id}`)).json();
      setAuto(p.project.policy ? p.project.policy.autopilot !== false : true);
    } catch {
      /* offline */
    }
    try {
      const s = await (await fetch(`${API}/api/projects/${id}/suggestions`)).json();
      setSugs(s.suggestions || []);
    } catch {
      /* offline */
    }
    setNotice(`Opened project ${id}.`);
  }

  async function runPlayground(save: boolean) {
    setBusy("Running…");
    setPlayOut("");
    try {
      const r = await fetch(`${API}/api/playground/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: playCode, ...(save ? { save_as: playName } : {}) }),
      });
      const j = await r.json();
      setPlayOut((j.output || j.error || "") + `\nexit: ${j.exit_code ?? "—"} · ${j.note || ""}`);
      win("run-playground");
      if (j.project) {
        setPid(j.project.id);
        setNotice(`Saved as project ${j.project.id} — files + ZIP appear in §5 after you Build; preview appears in §4.`);
        refreshTree(j.project.id);
      }
    } catch {
      setPlayOut("Backend offline.");
    }
    setBusy("");
  }

  function splitCmd(s: string): string[] {
    return (s.match(/"[^"]*"|\S+/g) || []).map((t) => t.replace(/^"|"$/g, ""));
  }

  async function requestTerm() {
    setTermOut("");
    setTermReq(null);
    if (!pid) return setNotice("Create a project first.");
    try {
      const j = await (
        await fetch(`${API}/api/projects/${pid}/terminal`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ argv: splitCmd(termCmd) }),
        })
      ).json();
      if (j.approval_id) setTermReq(j);
      else setNotice(j.error || "Rejected");
    } catch {
      setNotice("Backend offline.");
    }
  }

  async function approveTerm(ok: boolean) {
    if (!termReq || !pid) return;
    try {
      const j = await (
        await fetch(`${API}/api/projects/${pid}/terminal/approve`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ approval_id: termReq.approval_id, approved: ok }),
        })
      ).json();
      setTermOut(j.output || j.error || "Rejected.");
      setTermReq(null);
      refreshTree();
    } catch {
      setNotice("Backend offline.");
    }
  }

  async function loadSugs() {
    if (!pid) return setNotice("Create a project first.");
    try {
      const j = await (await fetch(`${API}/api/projects/${pid}/suggestions`)).json();
      setSugs(j.suggestions || []);
    } catch {
      setNotice("Backend offline.");
    }
  }

  async function openFile(path: string) {
    setSel(path);
    try {
      const r = await fetch(`${API}/api/projects/${pid}/files?path=${encodeURIComponent(path)}`);
      setCode((await r.json()).content || "");
    } catch {
      setCode("(offline)");
    }
  }

  async function upload(ev: React.ChangeEvent<HTMLInputElement>) {
    if (!pid || !ev.target.files?.[0]) return;
    const fd = new FormData();
    fd.append("file", ev.target.files[0]);
    setBusy("Uploading and inspecting…");
    try {
      const r = await fetch(`${API}/api/projects/${pid}/upload`, { method: "POST", body: fd });
      const j = await r.json();
      setNotice(j.ok ? `${j.summary}.` : `Rejected: ${j.error}`);
      refreshTree();
    } catch {
      setNotice("Upload failed — backend offline?");
    }
    setBusy("");
  }

  async function cloneGh() {
    if (!pid || !ghUrl.trim()) return;
    setBusy("Cloning…");
    try {
      const r = await fetch(`${API}/api/projects/${pid}/github/clone`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: ghUrl }),
      });
      const j = await r.json();
      setGhMsg(j.ok ? j.summary : `Failed: ${j.error || j.detail}`);
      refreshTree();
    } catch {
      setGhMsg("Backend offline.");
    }
    setBusy("");
  }

  async function openLocalFolder() {
    try {
      // @ts-expect-error File System Access API (Chromium)
      const dir = await window.showDirectoryPicker();
      const names: string[] = [];
      for await (const entry of dir.values()) names.push(entry.name);
      setLocalFiles(names.slice(0, 100));
      setNotice(`Reading local folder "${dir.name}" (${names.length} top-level entries). Local builds run on your machine via the setup guide.`);
    } catch {
      setNotice("Folder picker needs Chrome/Edge, and permission is yours to grant or deny.");
    }
  }

  const failed = report?.steps.filter((s) => !s.ok) || [];

  return (
    <div>
      <p className="crumb">studio — your AI software engineer</p>
      <h1 className="doctitle">Tell it. Watch it build. Take it home.</h1>
      <p className="docsub">
        You don&apos;t need to code. Describe the idea, and GENESIS generates,
        runs, tests, repairs and verifies — showing every step, never faking one.
      </p>
      <p className="docmeta">
        backend{" "}
        {online === null ? "…" : online ? <strong>online</strong> : <strong>OFFLINE — start it below</strong>}
      </p>

      <section>
        <h2 className="sect">0 · Dashboard</h2>
        {!dash ? (
          <p className="prose">Loading real numbers…</p>
        ) : (
          <>
            <p className="prose">
              <span className="hl">{dash.usage.projects} projects</span>{" "}
              <span className="hl">{dash.usage.verified} verified</span>{" "}
              <span className="hl">{dash.usage.builds} built</span>{" "}
              GitHub: {dash.github.ok ? `connected as @${dash.github.login}` : "not connected (public repos work anyway)"}
            </p>
            {dash.projects.map((p: any) => (
              <p className="prose" key={p.id}>
                <strong>{p.name}</strong> · {p.verdict} · {p.files} files{" "}
                <button type="button" className="btn" style={{ fontSize: 12, padding: "4px 12px" }} onClick={() => openProject(p.id)}>
                  Open
                </button>
              </p>
            ))}
            {dash.projects.length === 0 && <p className="prose">No projects yet — create one below.</p>}
          </>
        )}
      </section>

      <section>
        <h2 className="sect">1 · Start a project</h2>
        <p className="prose">
          <input
            value={pname}
            onChange={(e) => setPname(e.target.value)}
            aria-label="Project name"
            style={{ font: "inherit", fontSize: 12, padding: "6px 10px", borderRadius: 3, border: "1px solid var(--line2)", background: "#080b10", color: "inherit", width: "min(320px, 100%)" }}
          />{" "}
          <button type="button" className="hl" onClick={newProject}>▸ New project</button>
          {pid && <span className="prose" style={{ marginLeft: 12 }}>id: {pid}</span>}
        </p>
        <p>
          <button type="button" className={mode === "new" ? "btn primary" : "btn"} onClick={() => setMode("new")}>[1] build new</button>{" "}
          <button type="button" className={mode === "improve" ? "btn primary" : "btn"} onClick={() => setMode("improve")}>[2] improve existing</button>
        </p>
        <p className="prose">
          autopilot:{" "}
          <button type="button" className={auto ? "btn primary" : "btn"} onClick={() => flipAuto(!(auto ?? false))}>
            {auto ? "[on] aggressive — safe steps run at once" : auto === false ? "[off] ask me every time" : "[?] loading…"}
          </button>
        </p>
        {notice && <p className="prose"><span className="hl">note</span> {notice}</p>}
        {busy && <p className="prose">{busy}</p>}
      </section>

      <section>
        <h2 className="sect">{mode === "new" ? "2 · Describe what to build" : "2 · Describe the change"}</h2>
        {mode === "improve" && (
          <>
            <p className="prose">Upload your code first — Genesis inspects it and changes nothing without your approval. Then describe the change below.</p>
            <p><input type="file" accept=".zip" onChange={upload} aria-label="Upload ZIP project" /></p>
          </>
        )}
        <textarea className="spec" value={spec} onChange={(e) => setSpec(e.target.value)} rows={3} aria-label={mode === "new" ? "What to build" : "What to change"} />
        <p style={{ marginTop: 12 }}>
          <button type="button" className="btn primary" onClick={sendSpec}>Understand</button>{" "}
          <button type="button" className="btn" onClick={() => build("build")}>Build, run, test, verify</button>{" "}
          <button type="button" className="btn primary" onClick={() => build("fullstack")}>Build full app (frontend + API + DB)</button>
        </p>
        {reqs.length > 0 && (
          <ol className="rows">
            {reqs.map((r) => (
              <li key={r.id}><span /><span className={`g ${r.priority === "P0" ? "partial" : "done"}`}>{r.priority === "P0" ? "◐" : "●"}</span><span><span className="t">{r.id} — {r.description}</span></span></li>
            ))}
          </ol>
        )}
        {questions.length > 0 && (
          <div style={{ marginTop: 12 }}>
            <p className="prose"><span className="hl">stack choices</span> — only what changes the build; the rest takes the recommended default:</p>
            {questions.map((q: any) => (
              <div key={q.id} style={{ marginTop: 8 }}>
                <p className="prose">{q.ask} <span className="hl">why:</span> {q.why}</p>
                <p>
                  {q.options.map((o: any) => (
                    <span key={o.value} style={{ marginRight: 8 }}>
                      <button type="button"
                        className={answers[q.id] === o.value ? "btn primary" : "btn"}
                        onClick={() => setAnswers((a) => ({ ...a, [q.id]: o.value }))}
                        title={o.note}>{o.label}{q.recommended === o.value ? " ★" : ""}</button>
                    </span>
                  ))}
                </p>
                <p className="prose">{(q.options.find((o: any) => o.value === answers[q.id]) || {}).note}</p>
              </div>
            ))}
          </div>
        )}
      </section>

      <section>
        <h2 className="sect">3 · Chat about it</h2>
        {chat.map((m, i) => (
          <p className="prose" key={i}><strong>{m.who === "you" ? "You" : "Genesis"}:</strong> {m.text}</p>
        ))}
        <p>
          <input
            value={msg}
            onChange={(e) => setMsg(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && sendChat()}
            placeholder="Ask for a change, a feature, an explanation…"
            aria-label="Chat message"
            style={{ font: "inherit", fontSize: 12, padding: "6px 10px", borderRadius: 3, border: "1px solid var(--line2)", background: "#080b10", color: "inherit", width: "min(460px, 100%)" }}
          />{" "}
          <button type="button" className="btn" onClick={sendChat}>Send</button>
        </p>
      </section>

      <section>
        <h2 className="sect">4 · Watch it work</h2>
        {!report && <p className="prose">No build yet. Activity appears here step by step — install, start, test, review.</p>}
        {report && (
          <>
            <p className="prose">verdict: <span className="hl">{report.verdict}</span> {report.reason}</p>
            {report.decisions && (
              <div style={{ marginTop: 12 }}>
                <p className="prose"><span className="hl">stack decisions</span> why this shape:</p>
                <ol className="rows">
                  {report.decisions.map((d: any, i: number) => (
                    <li key={i}><span /><span className="g done">●</span><span><span className="t">{d.decision}</span><span className="e">{d.reason}</span></span></li>
                  ))}
                </ol>
              </div>
            )}
            <ol className="rows">
              {report.steps.map((s) => (
                <li key={s.step}><span /><span className={`g ${s.ok ? "done" : "queued"}`}>{s.ok ? "●" : "○"}</span><span><span className="t">{s.step}</span><span className="e">{s.detail}</span></span></li>
              ))}
            </ol>
          </>
        )}
      </section>

      <section>
        <h2 className="sect">5 · Files, tests, preview</h2>
        <p>
          <button type="button" className="btn" onClick={() => refreshTree()}>Refresh files</button>{" "}
          {pid && <a className="hl" href={`${API}/api/projects/${pid}/download`}>▸ Download ZIP</a>}
        </p>
        {files.length > 0 && (
          <p className="prose">
            {files.slice(0, 60).map((f) => (
              <span key={f}><button type="button" className={f === sel ? "hl" : "btn"} style={{ margin: "0 8px 8px 0", fontSize: 12 }} onClick={() => openFile(f)}>{f}</button></span>
            ))}
          </p>
        )}
        {sel && <pre className="out" style={{ maxHeight: 320, overflow: "auto" }}>{code.slice(0, 8000) || "(empty)"}</pre>}
        {report?.preview_url && (
          <div style={{ marginTop: 16 }}>
            <p className="prose"><span className="hl">live preview</span> {report.preview_url} (runs while this build lives)</p>
            <iframe src={report.preview_url} title="App preview" style={{ width: "100%", height: 320, border: "1px solid var(--line2)", borderRadius: 8, background: "#fff" }} sandbox="allow-scripts allow-same-origin" />
          </div>
        )}
        {failed.length > 0 && (
          <div style={{ marginTop: 16 }}>
            <p className="prose"><strong>Failed steps — nothing hidden:</strong></p>
            {failed.map((s) => (
              <pre className="out" key={s.step}>{s.step}: {s.detail}{"\n"}{s.evidence}</pre>
            ))}
            {report?.diagnosis && <pre className="out">diagnosis: {JSON.stringify(report.diagnosis, null, 1).slice(0, 1500)}</pre>}
          </div>
        )}
      </section>
      <section>
        <h2 className="sect">6 · Bring your own project</h2>
        <p className="prose"><strong>Upload a ZIP</strong> — inspected safely, never overwriting without permission.</p>
        <p><input type="file" accept=".zip" onChange={upload} aria-label="Upload ZIP project" /></p>
        <p className="prose" style={{ marginTop: 16 }}><strong>Connect GitHub</strong> — public repos clone free, no account. Pushing needs your approval + token. Account OAuth is not built; the API says so honestly.</p>
        <p>
          <input
            value={ghUrl}
            onChange={(e) => setGhUrl(e.target.value)}
            placeholder="https://github.com/owner/repo"
            aria-label="Repository URL"
            style={{ font: "inherit", fontSize: 12, padding: "6px 10px", borderRadius: 3, border: "1px solid var(--line2)", background: "#080b10", color: "inherit", width: "min(380px, 100%)" }}
          />{" "}
          <button type="button" className="btn" onClick={cloneGh}>Clone + inspect</button>
        </p>
        {ghMsg && <p className="prose">{ghMsg}</p>}
        <p className="prose" style={{ marginTop: 16 }}><strong>Local folder</strong> — picked by you, in your browser. Nothing uploaded.</p>
        <p><button type="button" className="btn" onClick={openLocalFolder}>Open local folder</button></p>
        {localFiles.length > 0 && <pre className="out">{localFiles.join("\n")}</pre>}
      </section>

      <section>
        <h2 className="sect">7 · Run it on your computer</h2>
        <p className="prose">Download the ZIP, then:</p>
        <pre className="out">Linux / macOS{"\n"}  python3 -m venv .venv && .venv/bin/pip install pytest{"\n"}  python3 app_server.py --port 8000{"\n  "}open http://127.0.0.1:8000{"\n\n"}Windows (PowerShell){"\n"}  py -m venv .venv; .\.venv\Scripts\pip install pytest{"\n"}  py app_server.py --port 8000</pre>
        <p className="prose">GENESIS never runs generated code on your machine without an isolated environment, and never does anything destructive without asking first.</p>
      <section>
        <h2 className="sect">8 · Playground</h2>
        <p className="prose">Run Python instantly (stdlib only, 20s limit) — or save it as a project and Build it properly with dependencies and tests.</p>
        <textarea className="spec" value={playCode} onChange={(e) => setPlayCode(e.target.value)} rows={5} aria-label="Playground code" />
        <p style={{ marginTop: 12 }}>
          <button type="button" className="btn primary" onClick={() => runPlayground(false)}>Run</button>{" "}
          <input
            value={playName}
            onChange={(e) => setPlayName(e.target.value)}
            aria-label="Save-as project name"
            style={{ font: "inherit", fontSize: 12, padding: "6px 10px", borderRadius: 3, border: "1px solid var(--line2)", background: "#080b10", color: "inherit", width: "min(280px, 100%)" }}
          />{" "}
          <button type="button" className="btn" onClick={() => runPlayground(true)}>Run + save as project</button>
        </p>
        {playOut && <pre className="out">{playOut}</pre>}
      </section>

      <section>
        <h2 className="sect">9 · Terminal</h2>
        <p className="prose">{auto ? "Autopilot on: safe commands (build, test, inspect) run immediately. Deletes, network exits and deploys still ask." : "Commands run server-side as argument lists — never a shell. Every command needs your explicit approval first, with the risks spelled out."}</p>
        <p>
          <input
            value={termCmd}
            onChange={(e) => setTermCmd(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && requestTerm()}
            aria-label="Terminal command"
            style={{ font: "inherit", fontSize: 12, padding: "6px 10px", borderRadius: 3, border: "1px solid var(--line2)", background: "#080b10", color: "inherit", width: "min(460px, 100%)" }}
          />{" "}
          <button type="button" className="btn" onClick={requestTerm}>Request</button>
        </p>
        {termReq && (
          <div>
            <p className="prose"><span className="hl">approval needed</span> {termReq.approval_id}</p>
            <pre className="out">
              what: {termReq.explanation.what}{"\n"}
              why: {termReq.explanation.why}{"\n"}
              changes: {termReq.explanation.changes}{"\n"}
              risks: {termReq.explanation.risks}{"\n"}
              rollback: {termReq.explanation.rollback}
            </pre>
            <p>
              <button type="button" className="btn primary" onClick={() => approveTerm(true)}>Approve + run</button>{" "}
              <button type="button" className="btn" onClick={() => approveTerm(false)}>Reject</button>
            </p>
          </div>
        )}
        {termOut && <pre className="out">{termOut}</pre>}
      </section>

      <section>
        <h2 className="sect">10 · Intelligence</h2>
        <p className="prose">GENESIS reads the actual project and says what it finds — missing tests, secrets, bloat, stale docs.</p>
        <p><button type="button" className="btn" onClick={loadSugs}>Analyze project</button></p>
        {sugs.length > 0 && (
          <ol className="rows">
            {sugs.map((s, i) => (
              <li key={i}><span /><span className={`g ${s.severity === "high" ? "queued" : s.severity === "medium" ? "partial" : "done"}`}>{s.severity === "high" ? "○" : s.severity === "medium" ? "◐" : "●"}</span><span><span className="t">[{s.severity}] {s.title}</span><span className="e">{s.detail}</span></span></li>
            ))}
          </ol>
        )}
      </section>

        {!online && (
          <pre className="out">Backend offline — start it:{"\n"}  cd "PROJECT GENESIS/backend" && python3 -m uvicorn app.api.server:app --port 8000{"\n"}Then reload this page.</pre>
        )}
      </section>
    </div>
  );
}
