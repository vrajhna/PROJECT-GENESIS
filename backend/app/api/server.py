"""Genesis HTTP API (Part XI, first slice): projects, chat, build, access.

Local-first: no auth on loopback (documented), Pydantic validation,
request IDs on every response, consistent error envelopes, SSE-ready
structure (long build runs synchronously in v1; events endpoint streams
the stored report steps).
"""

from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import (FileResponse, JSONResponse, PlainTextResponse,
                               StreamingResponse)
from pydantic import BaseModel, Field

from ..access import github as gh
from ..access.zips import inspect_tree, make_zip, safe_extract
from ..auth import accounts as accounts
from ..agents.roles import ArchitectAgent, ReviewerAgent
from ..builder.approvals import ApprovalGate
from ..builder.files import GenesisWorkspace
from ..builder.fullstack import (build_fullstack, detect_features, plan_questions,
                                 resolve_answers)
from ..builder.pipeline import build_and_verify
from ..intelligence.meta_client import MetaClient
from ..intelligence.model_router import ModelRouter
from ..intelligence import meta_health as _meta_health

# Meta health is checked ONCE in the background at startup (only when a key
# exists) and on explicit refresh — never per request, never blocking boot.
_meta_cache: dict = {"status": "unknown", "detail": "not checked yet",
                     "models": [], "missing": [], "latency_ms": 0}


def _refresh_meta_health() -> dict:
    import os as _os
    try:
        from ..intelligence.meta_client import MetaConfig as _MetaCfg
        cfg = _MetaCfg.from_env()
        res = _meta_health.meta_health(cfg.api_key, cfg.advanced_model,
                                       cfg.primary_model, cfg.base_url)
    except Exception as e:
        res = {"status": "unreachable", "detail": f"health check failed: {e}",
               "models": [], "missing": [], "latency_ms": 0}
    _meta_cache.clear()
    _meta_cache.update(res)
    return dict(_meta_cache)


def _start_meta_check() -> None:
    import os as _os
    # Local backend/.env is the documented dev flow — load it BEFORE the
    # check so a fresh key takes effect on plain restart (same rules as
    # _load_dotenv below: never overrides real env, never logged).
    try:
        import pathlib as _pl
        _root = _pl.Path(__file__).resolve().parent.parent.parent
        for _ln in (_root / ".env").read_text(encoding="utf-8").splitlines():
            _ln = _ln.strip()
            if not _ln or _ln.startswith("#") or "=" not in _ln:
                continue
            _k, _v = _ln.split("=", 1)
            _k, _v = _k.strip(), _v.strip().strip("'\"")
            if _k and _k not in _os.environ:
                _os.environ[_k] = _v
    except Exception:
        pass
    import threading as _th
    if not _os.environ.get("MODEL_API_KEY"):
        _meta_cache.update(status="no_key",
                           detail="MODEL_API_KEY is not set — model features off, "
                                  "templates carry every build")
        return
    _meta_cache.update(status="checking",
                       detail="checking Meta API in the background…")

    def _run() -> None:
        try:
            _refresh_meta_health()
        except Exception:
            pass
    try:
        t = _th.Thread(target=_run, daemon=True, name="genesis-meta-health")
        t.start()
    except Exception:
        pass


_start_meta_check()
from ..intelligence.prompt_manager import render

DATA_DIR = Path(__import__("os").environ.get("GENESIS_DATA_DIR", "/tmp/genesis-data"))

DATA_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Genesis", version="0.1.0")


def _cors_origins() -> list[str]:
    origins = ["http://localhost:3101", "http://127.0.0.1:3101",
               "http://localhost:3000", "http://127.0.0.1:3000"]
    try:
        import os
        extra = [o.strip() for o in os.environ.get("GENESIS_CORS_ORIGINS", "").split(",")]
        origins.extend(o for o in extra if o.startswith(("http://", "https://")))
    except Exception:
        pass
    return origins


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_methods=["*"], allow_headers=["*"],
    allow_credentials=True,
)


def _shared_allowed(ip: str, now: float, per_minute: int) -> bool | None:
    """Shared Postgres window (table genesis_hits) so limits hold across
    workers. Returns None when Postgres is absent/broken — the caller then
    uses the in-memory window instead. Never raises."""
    try:
        from ..db import pg as _pg
        con = _pg.connect()
        if con is None:
            return None
        try:
            _pg.ensure_schema(con)
            _pg.prune_hits(con, now - 60)
            n = _pg.count_recent(con, ip, now - 60)
            if n >= per_minute:
                return False
            _pg.hit(con, ip, now)
            return True
        finally:
            try:
                con.close()
            except Exception:
                pass
    except Exception:
        return None


class _RateLimiter:
    """Sliding window, shared across workers when Postgres is live.

    Loopback-only today, but the same box will serve webstudiobhiwadi.com
    tomorrow — limits already enforced."""

    def __init__(self, per_minute: int = 300) -> None:
        self.per_minute = per_minute
        self.hits: dict[str, list[float]] = {}

    def allowed(self, ip: str) -> bool:
        now = time.time()
        shared = _shared_allowed(ip, now, self.per_minute)
        if shared is not None:
            return shared
        window = [t for t in self.hits.get(ip, []) if now - t < 60]
        window.append(now)
        self.hits[ip] = window[-600:]
        if len(self.hits) > 1000:
            self.hits = {k: v for k, v in self.hits.items() if v and now - v[-1] < 60}
        return len(window) <= self.per_minute


RATE_LIMIT = _RateLimiter()


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    ip = request.client.host if request.client else "local"
    if not RATE_LIMIT.allowed(ip):
        return JSONResponse({"ok": False, "error": "rate limited: slow down"},
                            status_code=429)
    return await call_next(request)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = f"req-{uuid.uuid4().hex[:12]}"
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


def err(request: Request, message: str, status: int = 400) -> JSONResponse:
    return JSONResponse({"ok": False, "error": message,
                         "request_id": getattr(request.state, "request_id", "")},
                        status_code=status)


class StorageUnavailable(Exception):
    """Website strict mode cannot reach Postgres. Never fall back to files."""


@app.exception_handler(StorageUnavailable)
async def storage_unavailable_handler(request: Request, exc: StorageUnavailable):
    return JSONResponse({"ok": False,
                         "error": "database unavailable — website mode refuses file fallback",
                         "request_id": getattr(request.state, "request_id", "")},
                        status_code=503)


def strict_db() -> bool:
    """True only for website deployments: Postgres is the system of record."""
    if not require_db():
        return False
    try:
        from ..db import pg as _pgmod
        return bool(_pgmod.db_url() and _pgmod.available())
    except Exception:
        return False


def ensure_store() -> None:
    """Refuse website work when strict Postgres persistence is unavailable."""
    if require_db() and not strict_db():
        raise StorageUnavailable()


def _pg_conn():
    try:
        from ..db import pg as _pgmod
    except ImportError as e:
        raise StorageUnavailable() from e
    con = _pgmod.connect()
    if con is None:
        raise StorageUnavailable()
    return con


PID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _safe_pid(pid: str) -> bool:
    return bool(PID_RE.match(pid or ""))


def proj_dir(pid: str) -> Path:
    if not _safe_pid(pid):
        raise ValueError(f"bad project id: {pid!r}")
    return DATA_DIR / "projects" / pid


def load_project(pid: str) -> dict | None:
    if not _safe_pid(pid):
        return None
    if strict_db():
        from ..db import pg as _pgmod
        con = _pg_conn()
        try:
            try:
                doc = _pgmod.project_get(con, pid)
            except Exception as e:
                raise StorageUnavailable() from e
        finally:
            try:
                con.close()
            except Exception:
                pass
        return doc if isinstance(doc, dict) else None
    meta = proj_dir(pid) / "project.json"
    if not meta.exists():
        return None
    return json.loads(meta.read_text(encoding="utf-8"))


def save_project(meta: dict) -> None:
    doc = dict(meta or {})
    doc["updated"] = time.time()
    meta.update(doc)
    if strict_db():
        from ..db import pg as _pgmod
        if not _safe_pid(doc.get("id") or ""):
            raise ValueError(f"bad project id: {doc.get('id')!r}")
        con = _pg_conn()
        try:
            try:
                saved = _pgmod.project_save(con, doc)
            except Exception as e:
                raise StorageUnavailable() from e
        finally:
            try:
                con.close()
            except Exception:
                pass
        meta.update(saved)
        return
    d = proj_dir(doc["id"])
    d.mkdir(parents=True, exist_ok=True)
    (d / "project.json").write_text(json.dumps(doc, indent=2), encoding="utf-8")


def save_report(pid: str, report: dict) -> None:
    if strict_db():
        from ..db import pg as _pgmod
        con = _pg_conn()
        try:
            try:
                _pgmod.report_save(con, pid, report or {})
            except Exception as e:
                raise StorageUnavailable() from e
        finally:
            try:
                con.close()
            except Exception:
                pass
        return
    (proj_dir(pid) / "report.json").write_text(
        json.dumps(report or {}, indent=2), encoding="utf-8")


def load_report(pid: str) -> dict | None:
    if strict_db():
        from ..db import pg as _pgmod
        con = _pg_conn()
        try:
            try:
                doc = _pgmod.report_get(con, pid)
            except Exception as e:
                raise StorageUnavailable() from e
        finally:
            try:
                con.close()
            except Exception:
                pass
        return doc if isinstance(doc, dict) else None
    rep = proj_dir(pid) / "report.json"
    if not rep.exists():
        return None
    try:
        doc = json.loads(rep.read_text(encoding="utf-8"))
    except ValueError:
        return None
    return doc if isinstance(doc, dict) else None


class NewProject(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class SpecIn(BaseModel):
    spec: str = Field(min_length=1, max_length=8000)


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class CloneIn(BaseModel):
    url: str = Field(min_length=1, max_length=500)
    branch: str | None = None


class BranchIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class PushIn(BaseModel):
    branch: str = Field(min_length=1, max_length=100)
    approved: bool = False


class FullstackIn(BaseModel):
    answers: dict = Field(default_factory=dict)


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CLI_DIR = REPO_ROOT / "genesis-cli"


def _load_dotenv(path: Path) -> dict:
    """Parse KEY=value lines with stdlib only. Never overrides real environment."""
    import os
    found: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return found
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip("'\"")
        if k and k not in os.environ:
            os.environ[k] = v
            found[k] = v
    return found


_load_dotenv(REPO_ROOT / ".env")


def _zip_tree(base: Path, rels: list[str], arc_prefix: str) -> bytes:
    import io
    import zipfile
    buf = io.BytesIO()
    entries = 0
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in rels:
            p = base / rel
            if not p.exists():
                continue
            if p.is_dir():
                for f in sorted(p.rglob("*")):
                    if f.is_file() and "__pycache__" not in f.parts \
                            and f.suffix != ".pyc" and ".venv" not in f.parts \
                            and "node_modules" not in f.parts:
                        relpath = f.relative_to(base)
                        z.write(f, f"{arc_prefix}/{relpath}" if arc_prefix else str(relpath))
                        entries += 1
            else:
                z.write(p, f"{arc_prefix}/{rel}" if arc_prefix else rel)
                entries += 1
    # An empty zip is still 22 bytes — callers test truthiness to detect
    # missing packs, so empty must mean empty.
    return buf.getvalue() if entries else b""


@app.get("/api/health")
def health():
    mode = server_mode()
    if require_db() and mode != "server":
        return JSONResponse(
            {"ok": False, "service": "genesis", "mode": mode,
             "error": "DATABASE_URL required (GENESIS_REQUIRE_DB=1) — refusing file mode"},
            status_code=503)
    if require_db() and not strict_db():
        return JSONResponse(
            {"ok": False, "service": "genesis", "mode": mode,
             "error": "DATABASE_URL is not reachable (GENESIS_REQUIRE_DB=1) — refusing file mode"},
            status_code=503)
    db = "postgres" if mode == "server" else "sqlite/files"
    store = "postgres" if strict_db() else ("postgres-shared" if mode == "server" else "files")
    return {"ok": True, "service": "genesis", "time": time.time(),
            "mode": mode, "db": db, "store": store,
            "require_db": require_db(), "meta": dict(_meta_cache)}


@app.post("/api/settings/meta/check")
def meta_check(request: Request):
    """Re-run the Meta health probe on demand (bounded, synchronous)."""
    return {"ok": True, "meta": _refresh_meta_health()}


@app.post("/api/projects")
def create_project(body: NewProject, request: Request):
    me, error = need_member(request)
    if error is not None:
        return error
    pid = f"proj-{uuid.uuid4().hex[:8]}"
    meta = {"id": pid, "name": body.name, "spec": "", "created": time.time(),
            "policy": {"autopilot": True},
            "owner_email": "" if server_mode() == "local" else me["email"]}
    save_project(meta)
    return {"ok": True, "project": meta}


def _bearer(request: Request) -> str:
    try:
        return re.sub(r"^Bearer\s+", "",
                      str(request.headers.get("authorization") or ""))
    except Exception:
        return ""


def current_member(request: Request):
    """Logged-in member dict or None. Bearer token first, httpOnly cookie
    second. Never raises, never logs."""
    try:
        t = _bearer(request) or _cookie_token(request)
        return accounts.member_from_token(t) if t else None
    except Exception:
        return None


SESSION_COOKIE = "genesis_session"
CSRF_HEADER = "x-genesis-csrf"


def _cookie_secure(request: Request) -> bool:
    """Secure flag for the session cookie. SameSite=None is REJECTED by
    browsers without Secure — and behind proxies the scheme/proto headers
    are unreliable, so real (non-local) hostnames always get Secure.
    Localhost/test hosts stay plain so laptop mode keeps working."""
    try:
        proto = (request.headers.get("x-forwarded-proto") or "").split(",")[0].strip()
        if proto == "https" or request.url.scheme == "https":
            return True
        host = (request.url.hostname or "").lower()
        return host not in ("localhost", "127.0.0.1", "::1", "testserver", "")
    except Exception:
        return False


def _cookie_token(request: Request) -> str:
    try:
        return str(request.cookies.get(SESSION_COOKIE) or "")
    except Exception:
        return ""


def _uses_cookie_auth(request: Request) -> bool:
    return bool(_cookie_token(request)) and not _bearer(request)


def _csrf_ok(request: Request) -> bool:
    try:
        if not _uses_cookie_auth(request):
            return True
        if request.headers.get(CSRF_HEADER) != "1":
            return False
        from urllib.parse import urlsplit
        origin = request.headers.get("origin") or request.headers.get("referer") or ""
        host = (urlsplit(origin).hostname or "").lower() if origin else ""
        if not host:
            return False
        allowed = [urlsplit(o).hostname.lower() for o in _cors_origins() if "://" in o]
        return host in allowed
    except Exception:
        return False


def need_member(request: Request):
    ensure_store()
    if server_mode() == "local":
        # Laptop / terminal mode: your files, your machine — no login walls.
        # (Server mode always requires a real login; see below.)
        return {"email": "local@device", "name": "local"}, None
    me = current_member(request)
    if not me:
        return None, err(request, "join first — login to continue", 401)
    if request.method not in ("GET", "HEAD", "OPTIONS") and _uses_cookie_auth(request) and not _csrf_ok(request):
        return None, err(request, "forbidden — bad origin", 403)
    return me, None


def need_access(pid: str, request: Request):
    ensure_store()
    if server_mode() == "local":
        meta = load_project(pid)
        if meta is None:
            return None, None, err(request, "unknown project", 404)
        return {"email": "local@device", "name": "local"}, meta, None
    me, error = need_member(request)
    if error is not None:
        return None, None, error
    meta = load_project(pid)
    if meta is None:
        return None, None, err(request, "unknown project", 404)
    owner = meta.get("owner_email") or ""
    if owner and owner != me["email"]:
        return None, None, err(request, "not yours — private to its owner", 403)
    return me, meta, None


def server_mode() -> str:
    try:
        from ..db import pg as _pgmod
        return "server" if _pgmod.db_url() else "local"
    except Exception:
        return "local"


def require_db() -> bool:
    import os as _osmod
    return _osmod.environ.get("GENESIS_REQUIRE_DB") == "1"


class AuthEmailIn(BaseModel):
    email: str = Field(min_length=3, max_length=120)


class AuthVerifyIn(BaseModel):
    email: str = Field(min_length=3, max_length=120)
    code: str = Field(min_length=4, max_length=12)
    name: str | None = Field(default=None, max_length=60)


@app.post("/api/auth/request")
def auth_request(body: AuthEmailIn, request: Request):
    try:
        accounts.request_otp(body.email)
    except accounts.AuthFail as e:
        return err(request, e.message, e.status)
    return {"ok": True, "sent": True}


@app.post("/api/auth/verify")
def auth_verify(body: AuthVerifyIn, request: Request):
    try:
        out = accounts.verify_otp(body.email, body.code, body.name)
    except accounts.NeedProfile as e:
        return JSONResponse({"ok": False, "error": e.message,
                             "needProfile": True,
                             "request_id": getattr(request.state, "request_id", "")},
                            status_code=400)
    except accounts.AuthFail as e:
        return err(request, e.message, e.status)
    resp = JSONResponse({"ok": True, "token": out["token"],
                         "member": out["member"], "new": out["new"]})
    resp.set_cookie(SESSION_COOKIE, out["token"], max_age=30 * 24 * 3600,
                    path="/", httponly=True,
                    samesite="none" if _cookie_secure(request) else "lax",
                    secure=_cookie_secure(request))
    return resp


@app.get("/api/me")
def auth_me(request: Request):
    me = current_member(request)
    if not me:
        return err(request, "join first — login to continue", 401)
    return {"ok": True, "member": me}


@app.post("/api/auth/logout")
def auth_logout(request: Request):
    accounts.logout(_bearer(request) or _cookie_token(request))
    resp = JSONResponse({"ok": True})
    resp.set_cookie(SESSION_COOKIE, "", max_age=0, path="/", httponly=True,
                    samesite="none" if _cookie_secure(request) else "lax",
                    secure=_cookie_secure(request))
    return resp


@app.delete("/api/projects/{pid}")
def delete_project(pid: str, request: Request):
    me, error = need_member(request)
    if error is not None:
        return error
    meta = load_project(pid)
    if meta is None:
        return err(request, "unknown project", 404)
    owner = meta.get("owner_email") or ""
    if server_mode() != "local" and owner != me["email"]:
        if not owner:
            return err(request, "claim it first, then delete it", 403)
        return err(request, "not yours — only the owner can delete it", 403)
    import shutil
    slug = (meta.get("publish") or {}).get("slug") or ""
    if slug and SLUG_RE.match(slug):
        try:
            target = PUBLISH_DIR / slug
            if target.is_dir():
                shutil.rmtree(target)
        except OSError:
            pass
        idx = _publishes_index()
        idx.pop(slug, None)
        _save_publishes_index(idx)
    if strict_db():
        from ..db import pg as _pgmod
        con = _pg_conn()
        try:
            try:
                _pgmod.project_delete(con, pid)
            except Exception as e:
                raise StorageUnavailable() from e
        finally:
            try:
                con.close()
            except Exception:
                pass
    try:
        target = proj_dir(pid)
        base = (DATA_DIR / "projects").resolve()
        if target.resolve() != base and base in target.resolve().parents:
            shutil.rmtree(target)
        else:
            return err(request, "refusing to delete outside projects", 500)
    except (OSError, ValueError) as e:
        return err(request, f"delete failed: {e}", 500)
    return {"ok": True, "deleted": pid}


@app.post("/api/projects/{pid}/claim")
def claim_project(pid: str, request: Request):
    me, error = need_member(request)
    if error is not None:
        return error
    meta = load_project(pid)
    if meta is None:
        return err(request, "unknown project", 404)
    if meta.get("owner_email"):
        if meta["owner_email"] == me["email"]:
            return {"ok": True, "owner_email": me["email"], "already": True}
        return err(request, "already claimed by someone else", 403)
    meta["owner_email"] = me["email"]
    save_project(meta)
    return {"ok": True, "owner_email": me["email"]}


@app.get("/api/projects")
def list_projects(request: Request):
    """Your projects only (server mode). Laptop mode lists everything local.
    Logged out on the website sees nothing — empty, not an error."""
    me, error = need_member(request)
    if error is not None:
        return {"ok": True, "projects": []}
    if strict_db():
        from ..db import pg as _pgmod
        con = _pg_conn()
        try:
            try:
                docs = _pgmod.project_list(con)
            except Exception as e:
                raise StorageUnavailable() from e
        finally:
            try:
                con.close()
            except Exception:
                pass
        return {"ok": True, "projects": [
            m for m in docs
            if not (m.get("owner_email") or "") or m.get("owner_email") == me["email"]]}
    out = []
    base = DATA_DIR / "projects"
    if base.exists():
        for meta in sorted(base.glob("*/project.json")):
            try:
                m = json.loads(meta.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            owner = m.get("owner_email") or ""
            if owner and owner != me["email"]:
                continue
            out.append(m)
    return {"ok": True, "projects": out}


@app.get("/api/projects/{pid}")
def get_project(pid: str, request: Request):
    _, meta, error = need_access(pid, request)
    if error is not None:
        return error
    return {"ok": True, "project": meta}


def _set_dotenv_var(key: str, value: str) -> None:
    envf = REPO_ROOT / ".env"
    cur = envf.read_text(encoding="utf-8") if envf.exists() else ""
    out: list[str] = []
    seen = False
    for ln in cur.splitlines():
        if ln.strip().startswith(f"{key}="):
            if not seen:
                out.append(f"{key}={value}")
                seen = True
        else:
            out.append(ln)
    if not seen:
        out.append(f"{key}={value}")
    envf.write_text("\n".join(out) + "\n", encoding="utf-8")


class KeyIn(BaseModel):
    key: str = Field(min_length=8, max_length=500)


@app.post("/api/settings/key")
def set_key(body: KeyIn, request: Request):
    import os
    key = body.key.strip()
    if not key:
        return err(request, "empty key", 400)
    os.environ["MODEL_API_KEY"] = key
    try:
        _set_dotenv_var("MODEL_API_KEY", key)
    except OSError as e:
        return err(request, f"key live for this session, disk write failed: {e}", 500)
    return {"ok": True, "key_configured": True}


class DbIn(BaseModel):
    engine: str = Field(pattern="^(sqlite|postgres)$")
    url: str = Field(default="", max_length=2000)


@app.get("/api/settings/database")
def get_database():
    import os
    url = os.environ.get("DATABASE_URL", "")
    return {"ok": True, "engine": "postgres" if url else "sqlite",
            "live": "pending — reachable DB required" if url else "verified — zero setup",
            "require_db": require_db(), "strict": strict_db()}


def _pg_reachable(url: str) -> tuple[bool, str]:
    """Real reachability probe: connect + SELECT 1 + ensure engine schema,
    5s cap. Never raises."""
    try:
        import psycopg2
    except ImportError:
        return False, "pending — psycopg2 not installed"
    try:
        from ..db import pg as _pg
        con = psycopg2.connect(url, connect_timeout=5)
        try:
            cur = con.cursor()
            cur.execute("SELECT 1")
            cur.fetchone()
            schema_ok = _pg.ensure_schema(con)
        finally:
            con.close()
        if not schema_ok:
            return False, "pending — connected but schema setup failed"
        return True, "verified — reachable, SELECT 1 ok, engine tables ready"
    except Exception as e:
        return False, f"pending — unreachable: {str(e)[:160]}"


@app.post("/api/settings/database")
def set_database(body: DbIn, request: Request):
    import os
    if body.engine == "postgres":
        if not body.url.startswith(("postgresql://", "postgres://")):
            return err(request, "postgres needs a postgresql:// URL", 400)
        if require_db():
            ok, live = _pg_reachable(body.url)
            if not ok:
                return err(request, f"website database not verified: {live}", 400)
            os.environ["DATABASE_URL"] = body.url
            try:
                _set_dotenv_var("DATABASE_URL", body.url)
            except OSError as e:
                return err(request, f"database live for this session, disk write failed: {e}", 500)
            return {"ok": True, "engine": "postgres", "live": live}
        os.environ["DATABASE_URL"] = body.url
        try:
            _set_dotenv_var("DATABASE_URL", body.url)
        except OSError as e:
            return err(request, f"database live for this session, disk write failed: {e}", 500)
        _, live = _pg_reachable(body.url)
        return {"ok": True, "engine": "postgres", "live": live}
    if require_db():
        return err(request, "website deployments require postgres — sqlite is laptop-only", 400)
    os.environ.pop("DATABASE_URL", None)
    return {"ok": True, "engine": "sqlite", "live": "verified — zero setup"}


class PolicyIn(BaseModel):
    autopilot: bool


@app.post("/api/projects/{pid}/policy")
def set_policy(pid: str, body: PolicyIn, request: Request):
    _, meta, error = need_access(pid, request)
    if error is not None:
        return error
    meta["policy"] = {"autopilot": body.autopilot}
    save_project(meta)
    return {"ok": True, "policy": meta["policy"]}


@app.post("/api/projects/{pid}/spec")
def set_spec(pid: str, body: SpecIn, request: Request):
    _, meta, error = need_access(pid, request)
    if error is not None:
        return error
    arch = ArchitectAgent().run(body.spec)
    if not arch.ok:
        return {"ok": True, "needs_clarification": True,
                "question": arch.summary, "requirements": []}
    meta["spec"] = body.spec
    save_project(meta)
    return {"ok": True, "requirements": arch.data["requirements"],
            "evidence": arch.evidence}


@app.post("/api/projects/{pid}/chat")
def chat(pid: str, body: ChatIn, request: Request):
    _, meta, error = need_access(pid, request)
    if error is not None:
        return error
    text = body.message.strip()
    if len(text) < 20 and not meta.get("spec"):
        return {"ok": True, "mode": "clarify",
                "reply": "Tell me a little more — what should the software do, and who is it for? One or two sentences is enough to start."}
    arch = ArchitectAgent().run(meta.get("spec") + "\n" + text if meta.get("spec") else text)
    if not arch.ok:
        return {"ok": True, "mode": "clarify", "reply": arch.summary}
    reply = (f"I see {len(arch.data['requirements'])} requirement(s): "
             + "; ".join(r["id"] + " " + r["description"][:60] for r in arch.data["requirements"])
             + ". Press Build and I will generate, install, start, test and verify — showing every step.")
    client = MetaClient()
    model_error = ""
    if client.config.api_key:
        try:
            _, prompt = render("plan.make", {"requirements": json.dumps(arch.data["requirements"])})
            routed = ModelRouter(client).run("routine codegen", prompt[:2000])
            if routed.get("ok"):
                from ..builder.codegen import extract_text as _extract_text
                note = _extract_text(routed.get("data") or {}).strip().replace("\n", " ")[:400]
                if note:
                    reply += " (Model note: " + note + ")"
            else:
                model_error = str(routed.get("error") or "model call failed")[:300]
        except Exception as e:
            model_error = f"{type(e).__name__}: {e}"[:300]
    out = {"ok": True, "mode": "plan", "reply": reply,
           "requirements": arch.data["requirements"]}
    if model_error:
        out["model_error"] = model_error
    return out


@app.post("/api/projects/{pid}/build")
def build_project(pid: str, request: Request):
    _, meta, error = need_access(pid, request)
    if error is not None:
        return error
    if not meta.get("spec"):
        return err(request, "set a specification first (POST spec)", 400)
    workdir = proj_dir(pid) / "work"
    report = build_and_verify(meta["spec"], workdir)
    save_report(pid, report)
    return {"ok": report["verdict"] == "VERIFIED", "report": report}


@app.get("/api/projects/{pid}/questions")
def fullstack_questions(pid: str, request: Request):
    _, meta, error = need_access(pid, request)
    if error is not None:
        return error
    if not meta.get("spec"):
        return err(request, "set a specification first (POST /spec)", 400)
    arch = ArchitectAgent().run(meta["spec"])
    if not arch.ok:
        return err(request, arch.summary, 422)
    reqs = arch.data["requirements"]
    features = detect_features(reqs)
    return {"ok": True, "questions": plan_questions(reqs, features)}


@app.post("/api/projects/{pid}/fullstack")
def build_fullstack_app(pid: str, request: Request, body: FullstackIn | None = None,
                          stream: bool = False):
    _, meta, error = need_access(pid, request)
    if error is not None:
        return error
    assert meta is not None
    if not meta.get("spec"):
        return err(request, "set a specification first (POST /spec)", 400)
    answers = body.answers if body else {}
    try:
        chosen = resolve_answers(answers or None)
    except ValueError as e:
        return err(request, str(e), 400)
    workdir = proj_dir(pid) / "work"
    for stale in ("app.db", "app.log"):
        try:
            (workdir / stale).unlink()
        except OSError:
            pass
    if stream:
        # Live mode: the build runs in a background thread, steps stream
        # over SSE as agents finish them. Blocking mode below is unchanged.
        from ..orchestrator import runs as runstore

        def _run_fullstack(**kw):
            rep = build_fullstack(meta["spec"], workdir, answers=chosen, **kw)
            try:
                save_report(pid, rep)
            except OSError:
                pass
            return rep

        run_id = runstore.start_run(pid, "fullstack", _run_fullstack)
        return {"ok": True, "run_id": run_id,
                "stream_token": runstore.stream_token(run_id)}
    report = build_fullstack(meta["spec"], workdir, answers=chosen)
    save_report(pid, report)
    return {"ok": report["verdict"] == "VERIFIED", "report": report}


@app.get("/api/projects/{pid}/build/status")
def build_status(pid: str, request: Request, run_id: str = ""):
    from ..orchestrator import runs as runstore
    me, error = need_member(request)
    if error is not None:
        return error
    run = runstore.get_run(run_id)
    if not run or run["pid"] != pid:
        return err(request, "unknown run", 404)
    return {"ok": True, "run": {
        "id": run["id"], "pid": run["pid"], "kind": run["kind"],
        "status": run["status"], "steps": run["steps"],
        "error": run["error"], "started_at": run["started_at"],
        "report": run["report"],
    }}


@app.get("/api/projects/{pid}/build/stream")
def build_stream(pid: str, request: Request, run_id: str = "",
                 stoken: str = ""):
    from ..orchestrator import runs as runstore
    # Auth: session (cookie/Bearer) OR the run-scoped stream token —
    # EventSource cannot send headers, and cookie availability varies.
    if not runstore.check_stream_token(run_id, stoken):
        me, error = need_member(request)
        if error is not None:
            return error
    run = runstore.get_run(run_id)
    if not run or run["pid"] != pid:
        return err(request, "unknown run", 404)

    def events():
        yield f"event: start\ndata: {json.dumps({'run_id': run_id})}\n\n"
        idx = 0
        while True:
            snap = runstore.get_run(run_id)
            if not snap:
                break
            while idx < len(snap["steps"]):
                st = snap["steps"][idx]
                idx += 1
                yield f"event: step\ndata: {json.dumps(st)}\n\n"
            if snap["status"] in ("done", "failed"):
                yield ("event: done\ndata: " + json.dumps({
                    "status": snap["status"], "report": snap["report"],
                    "error": snap["error"]}) + "\n\n")
                break
            runstore.wait_done(run_id, timeout=10)
            yield ": hb\n\n"  # heartbeat: proxies kill silent SSE connections
    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


@app.get("/api/intelligence/status")
def intelligence_status():
    import os
    from ..agents import roles as _roles
    from ..tools.registry import TOOLS
    agents = sorted(n for n in dir(_roles) if n.endswith("Agent"))
    try:
        if strict_db():
            from ..db import pg as _pgmod
            con = _pg_conn()
            try:
                registry = _pgmod.kv_get(con, "skills:registry")
            finally:
                try:
                    con.close()
                except Exception:
                    pass
            skill_ids = sorted(registry) if isinstance(registry, dict) else []
        else:
            from ..memory.skill_registry import SkillRegistry
            skill_ids = [s.id for s in SkillRegistry(DATA_DIR / "skills.json").list()]
    except StorageUnavailable:
        raise
    except Exception:
        skill_ids = []
    return {"ok": True,
            "models": {"primary": os.environ.get("META_PRIMARY_MODEL", "muse-spark-1.3"),
                       "advanced": os.environ.get("META_ADVANCED_MODEL", "muse-wonder-1.0"),
                       "key_configured": bool(os.environ.get("MODEL_API_KEY")),
                       "key_url": os.environ.get("META_KEY_URL", "")},
            "agents": agents,
            "tools": {"count": len(TOOLS), "names": [t.name for t in TOOLS]},
            "skills": {"count": len(skill_ids), "ids": skill_ids}}


@app.get("/api/download/install.sh")
def download_install_sh():
    p = CLI_DIR / "install.sh"
    if not p.is_file():
        return JSONResponse({"ok": False, "error": "installer missing on server"},
                            status_code=500)
    return PlainTextResponse(p.read_text(encoding="utf-8"),
                             headers={"Content-Disposition": "attachment; filename=install.sh"})


@app.get("/api/download/install.ps1")
def download_install_ps1():
    p = CLI_DIR / "install.ps1"
    if not p.is_file():
        return JSONResponse({"ok": False, "error": "installer missing on server"},
                            status_code=500)
    return PlainTextResponse(p.read_text(encoding="utf-8"),
                             headers={"Content-Disposition": "attachment; filename=install.ps1"})


@app.get("/api/download/cli")
def download_cli():
    blob = _zip_tree(REPO_ROOT, ["genesis-cli"], "")
    if not blob:
        return JSONResponse({"ok": False, "error": "cli pack missing on server"}, status_code=500)
    return StreamingResponse(iter([blob]), media_type="application/zip",
                             headers={"Content-Disposition": "attachment; filename=genesis-cli.zip"})


@app.get("/api/download/engine")
def download_engine():
    blob = _zip_tree(REPO_ROOT, ["app", "tests", "genesis-cli",
                                 "requirements.txt", "README.md", ".env.example"], "genesis-engine")
    if not blob:
        return JSONResponse({"ok": False, "error": "engine pack missing on server"}, status_code=500)
    return StreamingResponse(iter([blob]), media_type="application/zip",
                             headers={"Content-Disposition": "attachment; filename=genesis-engine.zip"})


@app.get("/api/projects/{pid}/report")
def get_report(pid: str, request: Request):
    _, _, error = need_access(pid, request)
    if error is not None:
        return error
    report = load_report(pid)
    if report is None:
        return err(request, "no build yet", 404)
    return {"ok": True, "report": report}


@app.get("/api/runs/{pid}/events")
def run_events(pid: str, request: Request):
    _, _, error = need_access(pid, request)
    if error is not None:
        return error
    report = load_report(pid)
    steps = report.get("steps", []) if isinstance(report, dict) else []

    def gen():
        yield f"data: {json.dumps({'type': 'hello', 'project': pid})}\n\n"
        for s in steps:
            yield f"data: {json.dumps({'type': 'step', **s})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/api/projects/{pid}/tree")
def tree(pid: str, request: Request):
    _, _, error = need_access(pid, request)
    if error is not None:
        return error
    return {"ok": True, "files": inspect_tree(proj_dir(pid) / "work")}


@app.get("/api/projects/{pid}/files")
def read_file(pid: str, path: str, request: Request):
    _, _, error = need_access(pid, request)
    if error is not None:
        return error
    try:
        content = GenesisWorkspace(proj_dir(pid) / "work").read_file(path)
    except (ValueError, OSError) as e:
        return err(request, str(e), 400)
    return {"ok": True, "path": path, "content": content[:20000]}


@app.post("/api/projects/{pid}/upload")
async def upload_zip(pid: str, request: Request, file: UploadFile):
    _, _, error = need_access(pid, request)
    if error is not None:
        return error
    data = await file.read()
    if len(data) > 100 * 1024 * 1024:
        return err(request, "zip too large (100 MB cap)", 400)
    try:
        names = safe_extract(data, proj_dir(pid) / "work")
    except ValueError as e:
        return err(request, f"rejected archive: {e}", 400)
    except Exception as e:
        return err(request, f"unreadable archive: {type(e).__name__}", 400)
    return {"ok": True, "files": names, "summary": f"{len(names)} file(s) extracted"}


@app.get("/api/projects/{pid}/download")
def download_zip(pid: str, request: Request):
    _, _, error = need_access(pid, request)
    if error is not None:
        return error
    from fastapi.responses import Response
    blob = make_zip(proj_dir(pid) / "work")
    return Response(blob, media_type="application/zip",
                    headers={"Content-Disposition": f"attachment; filename={pid}.zip"})


PUBLISH_DIR = DATA_DIR / "published"
PUBLISH_MAX_BYTES = 20 * 1024 * 1024
PUBLISH_MAX_FILES = 2000
PUBLISH_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json",
    ".txt": "text/plain; charset=utf-8",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".map": "application/json",
}
SLUG_RE = re.compile(r"^[a-z0-9-]{1,80}$")


def _slugify(name: str, pid: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", str(name or "").lower()).strip("-")
    base = base[:40].strip("-") or "app"
    return f"{base}-{pid[-6:]}"


def _publishes_index() -> dict:
    if strict_db():
        from ..db import pg as _pg
        con = _pg_conn()
        try:
            try:
                v = _pg.kv_get(con, "publishes:index")
            except Exception as e:
                raise StorageUnavailable() from e
        finally:
            try:
                con.close()
            except Exception:
                pass
        return v if isinstance(v, dict) else {}
    try:
        from ..db import pg as _pg
        con = _pg.connect()
        if con is not None:
            try:
                v = _pg.kv_get(con, "publishes:index")
                if isinstance(v, dict):
                    return v
            finally:
                try:
                    con.close()
                except Exception:
                    pass
    except Exception:
        pass
    try:
        return json.loads((PUBLISH_DIR / "publishes.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_publishes_index(idx: dict) -> None:
    if strict_db():
        from ..db import pg as _pg
        con = _pg_conn()
        try:
            try:
                _pg.ensure_schema(con)
                _pg.kv_set(con, "publishes:index", idx)
            except Exception as e:
                raise StorageUnavailable() from e
        finally:
            try:
                con.close()
            except Exception:
                pass
        return
    try:
        from ..db import pg as _pg
        con = _pg.connect()
        if con is not None:
            try:
                _pg.ensure_schema(con)
                _pg.kv_set(con, "publishes:index", idx)
                return
            finally:
                try:
                    con.close()
                except Exception:
                    pass
    except Exception:
        pass
    try:
        PUBLISH_DIR.mkdir(parents=True, exist_ok=True)
        (PUBLISH_DIR / "publishes.json").write_text(json.dumps(idx, indent=2), encoding="utf-8")
    except OSError:
        pass


def _copy_publishable(src: Path, dest: Path) -> int:
    """Copy a static frontend tree. Guards: size cap, file cap, no dotfiles,
    no caches/venvs/node_modules. Returns file count. Raises ValueError."""
    import shutil
    if not (src / "index.html").is_file():
        raise ValueError("nothing publishable — build a static frontend first (needs index.html)")
    files: list[Path] = []
    total = 0
    for f in sorted(src.rglob("*")):
        if not f.is_file() or f.is_symlink():
            continue
        rel = f.relative_to(src)
        if any(part.startswith(".") or part in ("__pycache__", "node_modules", ".venv", "venv")
               for part in rel.parts):
            continue
        if f.suffix == ".pyc":
            continue
        total += f.stat().st_size
        files.append(f)
    if total > PUBLISH_MAX_BYTES:
        raise ValueError("too big to publish (20 MB cap on static sites)")
    if len(files) > PUBLISH_MAX_FILES:
        raise ValueError("too many files to publish (2000 cap)")
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    for f in files:
        rel = f.relative_to(src)
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, target)
    return len(files)


class PublishIn(BaseModel):
    slug: str | None = Field(default=None, max_length=80)


@app.post("/api/projects/{pid}/publish")
def publish_project(pid: str, body: PublishIn, request: Request):
    me, error = need_member(request)
    if error is not None:
        return error
    meta = load_project(pid)
    if meta is None:
        return err(request, "unknown project", 404)
    owner = meta.get("owner_email") or ""
    if owner and owner != me["email"]:
        return err(request, "not yours — only the owner can publish it", 403)
    src = proj_dir(pid) / "work" / "frontend"
    raw = (body.slug or "").strip().lower()
    if raw:
        if not SLUG_RE.match(raw):
            return err(request, "slug must be letters, numbers and dashes", 400)
        slug = raw
    else:
        slug = _slugify(meta.get("name") or "app", pid)
    idx = _publishes_index()
    taken = idx.get(slug)
    if taken and taken.get("pid") != pid:
        return err(request, f"slug taken — pick another one", 409)
    try:
        n = _copy_publishable(src, PUBLISH_DIR / slug)
    except ValueError as e:
        return err(request, str(e), 400)
    except OSError:
        return err(request, "storage unavailable", 500)
    meta["owner_email"] = me["email"]
    meta["publish"] = {"slug": slug, "at": int(time.time()), "files": n,
                       "url": f"/p/{slug}/"}
    save_project(meta)
    idx[slug] = {"pid": pid, "owner": me["email"], "at": int(time.time())}
    _save_publishes_index(idx)
    return {"ok": True, "slug": slug, "files": n, "url": f"/p/{slug}/"}


@app.delete("/api/projects/{pid}/publish")
def unpublish_project(pid: str, request: Request):
    me, error = need_member(request)
    if error is not None:
        return error
    meta = load_project(pid)
    if meta is None:
        return err(request, "unknown project", 404)
    owner = meta.get("owner_email") or ""
    if owner != me["email"]:
        return err(request, "not yours — only the owner can unpublish it", 403)
    slug = (meta.get("publish") or {}).get("slug") or ""
    import shutil
    if slug and SLUG_RE.match(slug):
        try:
            target = PUBLISH_DIR / slug
            if target.is_dir():
                shutil.rmtree(target)
        except OSError:
            pass
        idx = _publishes_index()
        idx.pop(slug, None)
        _save_publishes_index(idx)
    meta.pop("publish", None)
    save_project(meta)
    return {"ok": True, "unpublished": True}


@app.get("/p/{slug}")
def published_root(slug: str):
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=f"/p/{slug}/", status_code=302)


@app.get("/p/{slug}/{rest:path}")
def published_site(slug: str, rest: str):
    from fastapi.responses import FileResponse, Response
    if not SLUG_RE.match(slug or ""):
        return Response("Not Found", status_code=404, media_type="text/plain")
    base = (PUBLISH_DIR / slug).resolve()
    try:
        target = (base / (rest or "")).resolve()
    except (OSError, ValueError):
        return Response("Not Found", status_code=404, media_type="text/plain")
    if base != target and base not in target.parents:
        return Response("Not Found", status_code=404, media_type="text/plain")
    if target.is_dir():
        target = target / "index.html"
    if not target.is_file():
        # SPA fallback: extensionless deep links resolve to index.html
        fallback = base / "index.html"
        if "." not in Path(rest or "").name and fallback.is_file():
            target = fallback
        else:
            return Response("Not Found", status_code=404, media_type="text/plain")
    ctype = PUBLISH_TYPES.get(target.suffix.lower(), "application/octet-stream")
    return FileResponse(str(target), media_type=ctype)


@app.post("/api/projects/{pid}/github/clone")
def github_clone(pid: str, body: CloneIn, request: Request):
    _, _, error = need_access(pid, request)
    if error is not None:
        return error
    res = gh.clone(body.url, proj_dir(pid) / "work", branch=body.branch)
    if not res.get("ok"):
        raise HTTPException(400, res.get("error", "clone failed"))
    return {"ok": True, **res}


@app.get("/api/projects/{pid}/github/branches")
def github_branches(pid: str, request: Request):
    _, _, error = need_access(pid, request)
    if error is not None:
        return error
    return gh.list_branches(proj_dir(pid) / "work")


@app.post("/api/projects/{pid}/github/branch")
def github_branch(pid: str, body: BranchIn, request: Request):
    _, _, error = need_access(pid, request)
    if error is not None:
        return error
    res = gh.create_branch(proj_dir(pid) / "work", body.name)
    if not res.get("ok"):
        raise HTTPException(400, res.get("error", "branch failed"))
    return {"ok": True, **res}


@app.get("/api/projects/{pid}/github/diff")
def github_diff(pid: str, request: Request, base: str = "HEAD"):
    _, _, error = need_access(pid, request)
    if error is not None:
        return {"ok": False, "error": "private project — join to inspect it"}
    res = gh.diff_summary(proj_dir(pid) / "work", base=base)
    res.update(gh.run_tests_first(proj_dir(pid) / "work"))
    return res


@app.post("/api/projects/{pid}/github/push")
def github_push(pid: str, body: PushIn, request: Request):
    _, _, error = need_access(pid, request)
    if error is not None:
        return error
    res = gh.push(proj_dir(pid) / "work", body.branch, approved=body.approved)
    if not res.get("ok"):
        raise HTTPException(400, res.get("error", "push refused"))
    return {"ok": True, **res}


@app.get("/api/github/connect")
def github_connect():
    return gh.connect_account()


def _project_stats(pid: str) -> dict:
    base = proj_dir(pid)
    work = base / "work"
    files = inspect_tree(work) if work.exists() else []
    verdict, passed = "never-built", 0
    r = load_report(pid)
    if isinstance(r, dict):
        verdict = r.get("verdict", "unknown")
        passed = sum(1 for s in r.get("steps", []) if s.get("ok"))
    elif not strict_db() and (base / "report.json").exists():
        verdict = "corrupt-report"
    return {"files": len(files), "verdict": verdict, "steps_ok": passed}


@app.get("/api/dashboard")
def dashboard(request: Request):
    listed = list_projects(request)
    if not isinstance(listed, dict):
        # logged out on the website: empty board, not an error
        listed = {"ok": True, "projects": []}
    projs = listed["projects"]
    items, verified, total_passed = [], 0, 0
    for p in projs:
        st = _project_stats(p["id"])
        if st["verdict"] == "VERIFIED":
            verified += 1
            total_passed += st["steps_ok"]
        mtime = p.get("updated") or p.get("created") or 0
        if not mtime and not strict_db():
            try:
                mtime = (proj_dir(p["id"]) / "project.json").stat().st_mtime
            except OSError:
                pass
        items.append({**p, **st, "mtime": mtime})
    items.sort(key=lambda x: x["mtime"], reverse=True)
    return {"ok": True,
            "projects": items,
            "usage": {"projects": len(items), "verified": verified,
                      "builds": sum(1 for i in items if i["verdict"] != "never-built"),
                      "steps_passed": total_passed},
            "github": gh.connect_account()}


class RunCodeIn(BaseModel):
    code: str = Field(min_length=1, max_length=20000)
    save_as: str | None = None


@app.post("/api/playground/run")
def playground_run(body: RunCodeIn, request: Request):
    import subprocess
    import tempfile
    with tempfile.TemporaryDirectory(prefix="genesis-play-") as tmp:
        main = Path(tmp) / "main.py"
        main.write_text(body.code, encoding="utf-8")
        try:
            proc = subprocess.run(["python3", "main.py"], cwd=tmp,
                                  capture_output=True, text=True,
                                  timeout=20, shell=False)
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "20s time limit exceeded (stdlib only, no installs here)"}
        out = (proc.stdout + proc.stderr)[-4000:]
        result: dict = {"ok": proc.returncode == 0, "exit_code": proc.returncode,
                        "output": out, "note": "stdlib only; use Build for dependencies"}
        if body.save_as:
            me, error = need_member(request)
            if error is not None:
                return err(request, "join first — login to save projects", 401)
            meta = {"id": f"proj-{uuid.uuid4().hex[:8]}", "name": body.save_as,
                    "spec": "Playground experiment.", "created": time.time(),
                    "owner_email": me["email"]}
            save_project(meta)
            (proj_dir(meta["id"]) / "work").mkdir(parents=True, exist_ok=True)
            GenesisWorkspace(proj_dir(meta["id"]) / "work").create_file("main.py", body.code)
            result["project"] = meta
        return result


_gates: dict[str, ApprovalGate] = {}
_pending_argv: dict[str, list[str]] = {}


_SAFE_BINS = {"python3", "python", "pytest", "pip", "ls", "cat", "echo", "pwd",
              "git", "npm", "node", "find", "grep", "head", "tail", "wc", "diff",
              "unzip", "zip", "lsb_release", "whoami"}
_DENY_TOKENS = {"push", "deploy", "publish", "release", "curl", "wget", "ssh",
                "scp", "sftp", "ftp", "telnet", "rm", "rmdir", "clone", "kill",
                "killall", "reboot", "shutdown", "halt", "poweroff", "mkfs",
                "dd", "chmod", "chown", "sudo", "su", "passwd"}


def _auto_runnable(argv: list[str]) -> bool:
    """Autopilot may run read-only and project-local build/test commands at once.
    Anything that deletes, leaves the machine, escalates, or touches the network
    beyond dependency installs still needs explicit approval."""
    if not argv or argv[0] not in _SAFE_BINS:
        return False
    for tok in argv:
        if any(c in tok for c in ";|&$`><()"):
            return False
        if tok.lower() in _DENY_TOKENS:
            return False
    return True


_TERMINAL_ENV_ALLOW = {"PATH", "HOME", "LANG", "LC_ALL", "TERM", "TZ",
                         "PYTHONDONTWRITEBYTECODE", "PYTHONHASHSEED",
                         "NODE_PATH", "NPM_CONFIG_CACHE"}


def _exec_terminal(pid: str, argv: list[str]) -> dict:
    import os
    import subprocess
    (proj_dir(pid) / "work").mkdir(parents=True, exist_ok=True)
    # Allowlist env: terminal children must never see server secrets
    # (MODEL_API_KEY, DATABASE_URL, tokens) even if a command prints environ.
    env = {k: v for k, v in os.environ.items() if k in _TERMINAL_ENV_ALLOW}
    env.setdefault("PATH", "/usr/bin:/bin")
    try:
        proc = subprocess.run(argv, cwd=str(proj_dir(pid) / "work"),
                              capture_output=True, text=True, timeout=30,
                              shell=False, env=env)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "30s time limit exceeded"}
    except FileNotFoundError as e:
        return {"ok": False, "error": f"command not found: {e}"}
    out = (proc.stdout + proc.stderr)[-4000:]
    return {"ok": proc.returncode == 0, "exit_code": proc.returncode, "output": out}


class TermIn(BaseModel):
    argv: list[str] = Field(min_length=1, max_length=20)


class TermApprove(BaseModel):
    approval_id: str
    approved: bool


@app.post("/api/projects/{pid}/terminal")
def terminal_request(pid: str, body: TermIn, request: Request):
    _, meta, error = need_access(pid, request)
    if error is not None:
        return error
    if server_mode() != "local":
        return err(request, "terminal execution runs on laptop/CLI mode only — "
                            "on the website, code runs inside verified Docker "
                            "builds (sandboxed terminal is tracked future work)",
                   403)
    if not all(isinstance(a, str) for a in body.argv) or len(" ".join(body.argv)) > 2000:
        return err(request, "argv must be a list of short strings (no shell)", 400)
    if (meta.get("policy") or {}).get("autopilot") and _auto_runnable(body.argv):
        res = _exec_terminal(pid, body.argv)
        if res.get("error", "").startswith("command not found"):
            return err(request, res["error"], 400)
        res["autopilot"] = True
        return res
    gate = _gates.setdefault(pid, ApprovalGate())
    (proj_dir(pid) / "work").mkdir(parents=True, exist_ok=True)
    item = gate.request("run_command",
                        f"argv={' '.join(body.argv)} in {pid}/work (timeout 30s, no shell, output capped)")
    _pending_argv[item.id] = list(body.argv)
    return {"ok": True, "approval_id": item.id,
            "explanation": {
                "what": f"Run `{' '.join(body.argv)}` in this project's folder.",
                "why": "You asked for terminal execution.",
                "changes": "Runs in an isolated subprocess; may write files inside the project only.",
                "risks": "A malicious or mistaken command can damage project files. Nothing outside the project is reachable.",
                "rollback": "Use the project's Git checkpoint / restore flow before risky commands."},
            "options": ["approve", "reject"]}


@app.post("/api/projects/{pid}/terminal/approve")
def terminal_approve(pid: str, body: TermApprove, request: Request):
    _, _, error = need_access(pid, request)
    if error is not None:
        return error
    if server_mode() != "local":
        return err(request, "terminal execution runs on laptop/CLI mode only",
                   403)
    gate = _gates.setdefault(pid, ApprovalGate())
    if not body.approved:
        try:
            gate.reject(body.approval_id)
        except (KeyError, ValueError):
            pass
        _pending_argv.pop(body.approval_id, None)
        return {"ok": False, "error": "rejected by user"}
    try:
        item = gate.approve(body.approval_id)
    except (KeyError, ValueError) as e:
        return err(request, f"bad approval id: {e}", 400)
    argv = _pending_argv.pop(body.approval_id, None)
    if argv is None:
        m = re.match(r"argv=(.*?) in .*?/work", item.detail)
        argv = (m.group(1) if m else "").split(" ")
    res = _exec_terminal(pid, argv)
    if res.get("error", "").startswith("command not found"):
        return err(request, res["error"], 400)
    return res


@app.get("/api/projects/{pid}/suggestions")
def suggestions(pid: str, request: Request):
    _, _, error = need_access(pid, request)
    if error is not None:
        return error
    work = proj_dir(pid) / "work"
    out: list[dict] = []
    if not work.exists() or not any(work.iterdir()):
        return {"ok": True, "suggestions": [{
            "severity": "info", "title": "Empty project",
            "detail": "Describe the idea above and press Build, or upload a ZIP.",
            "action": "spec"}]}
    import subprocess as _sp
    has_tests = any(work.glob("test_*.py")) or any(work.glob("*_test.py"))
    if not has_tests:
        out.append({"severity": "high", "title": "No tests present",
                    "detail": "Nothing here can be verified. Generate tests before claiming anything works.",
                    "action": "build"})
    else:
        try:
            p = _sp.run(["python3", "-m", "pytest", "-q", "--collect-only"],
                        cwd=str(work), capture_output=True, text=True, timeout=60, shell=False)
            import re as _re
            m = _re.search(r"(\d+) tests? collected", (p.stdout + p.stderr))
            out.append({"severity": "info" if p.returncode == 0 else "high",
                        "title": f"{m.group(1) if m else '?'} tests collected" if p.returncode == 0 else "Test collection fails",
                        "detail": "Run the suite to see what passes.", "action": "build"})
        except Exception as e:
            out.append({"severity": "high", "title": "Cannot collect tests",
                        "detail": str(e)[:200], "action": "build"})
    if not (work / "README.md").exists() and not (work / "SETUP.md").exists():
        out.append({"severity": "medium", "title": "No setup docs",
                    "detail": "Nobody can run this without instructions. Export adds SETUP.md automatically.",
                    "action": "export"})
    todos = 0
    for f in work.rglob("*"):
        if f.is_file() and f.suffix in (".py", ".ts", ".tsx", ".js", ".md") and f.stat().st_size < 500000:
            try:
                todos += f.read_text(encoding="utf-8", errors="ignore").count("TODO")
            except OSError:
                continue
    if todos:
        out.append({"severity": "low", "title": f"{todos} TODO marker(s)",
                    "detail": "Unfinished business tracked in code comments.", "action": "review"})
    big = [str(f.relative_to(work)) for f in work.rglob("*")
           if f.is_file() and f.stat().st_size > 500000 and ".venv" not in f.parts]
    if big:
        out.append({"severity": "medium", "title": "Large files committed",
                    "detail": ", ".join(big[:5]) + " — generated artifacts should not live in the repo.",
                    "action": "review"})
    rev = ReviewerAgent().run(work)
    for finding in rev.data.get("findings", []):
        if "secret" in finding.lower() or "possible" in finding.lower():
            out.append({"severity": "high", "title": "Possible secret in code",
                        "detail": finding + " — move it to env vars.", "action": "review"})
    if not out:
        out.append({"severity": "info", "title": "Healthy baseline",
                    "detail": "Tests present, docs present, no secrets, no bloat.", "action": "none"})
    return {"ok": True, "suggestions": out}
