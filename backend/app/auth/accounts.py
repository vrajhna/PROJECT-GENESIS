"""Server accounts: email + OTP login, sessions. PaperOS-style, stdlib mail.

Storage: Postgres tables (genesis_users, genesis_otps, genesis_sessions)
when DATABASE_URL is live, else JSON files under GENESIS_DATA_DIR/accounts.
OTPs are sha256-hashed, 6 digits, 10-minute expiry, 5 tries then dead.
Request rate: 5 codes per 10 minutes per email. Sessions: 30-day bearer
tokens. Mail goes through smtplib (stdlib); without SMTP_* env the request
endpoint refuses honestly with 503 instead of pretending.

Nothing here ever prints or logs codes, tokens, or emails bodies.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import time
from pathlib import Path

OTP_TTL = 600
OTP_TRIES = 5
REQ_LIMIT = 5
REQ_WINDOW = 600
SESSION_TTL = 30 * 24 * 3600

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$")


class AuthFail(Exception):
    def __init__(self, status: int, message: str, extra: dict | None = None):
        super().__init__(message)
        self.status = status
        self.message = message
        self.extra = extra or {}


class NeedProfile(AuthFail):
    def __init__(self):
        super().__init__(400, "first login needs a name",
                         {"needProfile": True})


def valid_email(v: str) -> bool:
    return bool(EMAIL_RE.match(str(v or "").strip()[:120]))


def _now() -> int:
    return int(time.time())


def _root() -> Path:
    base = Path(os.environ.get("GENESIS_DATA_DIR", "/tmp/genesis-data"))
    d = base / "accounts"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _read_json(name: str, fallback):
    try:
        return json.loads((_root() / name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return fallback


def _write_json(name: str, value) -> bool:
    try:
        (_root() / name).write_text(json.dumps(value), encoding="utf-8")
        return True
    except OSError:
        return False


def _pg():
    try:
        from ..db import pg as _p
    except ImportError:
        return None
    try:
        con = _p.connect()
    except Exception:
        return None
    return con


def _otp_hash(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def _new_otp() -> str:
    return str(__import__("random").randint(100000, 999999))


# ---------- mail (stdlib smtplib equivalent: dynamic import, tested via fake)

def _smtp_config():
    host = os.environ.get("SMTP_HOST", "").strip()
    user = os.environ.get("SMTP_USER", "").strip()
    pwd = os.environ.get("SMTP_PASS", "")
    if not host or not user or not pwd:
        return None
    return {
        "host": host,
        "port": int(os.environ.get("SMTP_PORT") or 587),
        "user": user,
        "pwd": pwd,
        "from": os.environ.get("SMTP_FROM", "").strip() or user,
    }


def send_otp_mail(to: str, code: str, mailer=None) -> None:
    if mailer:
        mailer(to, code)
        return
    cfg = _smtp_config()
    if not cfg:
        raise AuthFail(503, "mail not configured yet — set SMTP_HOST/USER/PASS")
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Your Genesis login code"
    msg["From"] = cfg["from"]
    msg["To"] = to
    text = (f"Hi!\n\nYour Genesis login code is: {code}\n\n"
            "It works for 10 minutes. If you did not ask for it, ignore this mail.\n\n— Genesis")
    html = (f'<div style="max-width:480px;margin:0 auto;font-family:Georgia,serif;'
            f'color:#202122;background:#0B0B0F;border:1px solid #222;padding:24px;'
            f'text-align:center;color:#EDEDED"><div style="font-size:20px">Genesis</div>'
            f'<p style="font-family:Arial,sans-serif;font-size:13px;color:#999">'
            f'Your login code (valid 10 minutes):</p>'
            f'<div style="font-size:38px;letter-spacing:8px;font-weight:bold">{code}</div></div>')
    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))
    try:
        if cfg["port"] == 465:
            smtp = smtplib.SMTP_SSL(cfg["host"], cfg["port"], timeout=15)
        else:
            smtp = smtplib.SMTP(cfg["host"], cfg["port"], timeout=15)
        try:
            smtp.starttls()
        except smtplib.SMTPException:
            pass
        smtp.login(cfg["user"], cfg["pwd"])
        smtp.sendmail(cfg["from"], [to], msg.as_string())
    except Exception as e:
        raise AuthFail(502, f"mail send failed: {str(e)[:120]}")
    finally:
        try:
            smtp.quit()
        except Exception:
            pass


# ---------- stores (pg first, files fallback)

def _file_get(table: str, key: str):
    return (_read_json(table + ".json", {}) or {}).get(key)


def _file_put(table: str, key: str, val) -> bool:
    data = _read_json(table + ".json", {}) or {}
    data[key] = val
    return _write_json(table + ".json", data)


def _file_del(table: str, key: str) -> bool:
    data = _read_json(table + ".json", {}) or {}
    if key not in data:
        return False
    del data[key]
    return _write_json(table + ".json", data)


def _store_otp(email: str, rec: dict) -> None:
    con = _pg()
    if con is not None:
        try:
            from ..db import pg as _p
            _p.ensure_schema(con)
            cur = con.cursor()
            try:
                cur.execute(
                    "INSERT INTO genesis_otps (email, hash, exp, tries, count, window_start)"
                    " VALUES (%s,%s,%s,%s,%s,%s)"
                    " ON CONFLICT (email) DO UPDATE SET hash=EXCLUDED.hash,"
                    " exp=EXCLUDED.exp, tries=EXCLUDED.tries,"
                    " count=EXCLUDED.count, window_start=EXCLUDED.window_start",
                    (email, rec["hash"], rec["exp"], rec["tries"],
                     rec["count"], rec["window_start"]))
                con.commit()
                return
            finally:
                cur.close()
                con.close()
        except Exception:
            pass
    if not _file_put("otps", email, rec):
        raise AuthFail(500, "storage unavailable")


def _load_otp(email: str):
    con = _pg()
    if con is not None:
        try:
            cur = con.cursor()
            try:
                cur.execute("SELECT hash, exp, tries, count, window_start"
                            " FROM genesis_otps WHERE email = %s", (email,))
                r = cur.fetchone()
            finally:
                cur.close()
                con.close()
            if r:
                return {"hash": r[0], "exp": r[1], "tries": r[2],
                        "count": r[3], "window_start": r[4]}
            return None
        except Exception:
            pass
    return _file_get("otps", email)


def _clear_otp(email: str) -> None:
    con = _pg()
    if con is not None:
        try:
            cur = con.cursor()
            try:
                cur.execute("DELETE FROM genesis_otps WHERE email = %s", (email,))
                con.commit()
            finally:
                cur.close()
                con.close()
        except Exception:
            pass
    _file_del("otps", email)


def _get_user(email: str):
    con = _pg()
    if con is not None:
        try:
            cur = con.cursor()
            try:
                cur.execute("SELECT email, name, created_at, last_login"
                            " FROM genesis_users WHERE email = %s", (email,))
                r = cur.fetchone()
            finally:
                cur.close()
                con.close()
            if r:
                return {"email": r[0], "name": r[1],
                        "createdAt": r[2], "lastLogin": r[3]}
            return None
        except Exception:
            pass
    return _file_get("users", email)


def _save_user(member: dict) -> None:
    con = _pg()
    if con is not None:
        try:
            from ..db import pg as _p
            _p.ensure_schema(con)
            cur = con.cursor()
            try:
                cur.execute(
                    "INSERT INTO genesis_users (email, name, created_at, last_login)"
                    " VALUES (%s,%s,%s,%s)"
                    " ON CONFLICT (email) DO UPDATE SET name=EXCLUDED.name,"
                    " last_login=EXCLUDED.last_login",
                    (member["email"], member["name"],
                     member.get("createdAt", _now()), _now()))
                con.commit()
                return
            finally:
                cur.close()
                con.close()
        except Exception:
            pass
    if not _file_put("users", member["email"], member):
        raise AuthFail(500, "storage unavailable")


def _save_session(token: str, email: str, exp: int) -> None:
    con = _pg()
    if con is not None:
        try:
            cur = con.cursor()
            try:
                cur.execute("INSERT INTO genesis_sessions (token, email, exp)"
                            " VALUES (%s,%s,%s) ON CONFLICT (token) DO NOTHING",
                            (token, email, exp))
                con.commit()
                return
            finally:
                cur.close()
                con.close()
        except Exception:
            pass
    if not _file_put("sessions", token, {"email": email, "exp": exp}):
        raise AuthFail(500, "storage unavailable")


def _load_session(token: str):
    con = _pg()
    if con is not None:
        try:
            cur = con.cursor()
            try:
                cur.execute("SELECT email, exp FROM genesis_sessions WHERE token = %s",
                            (token,))
                r = cur.fetchone()
            finally:
                cur.close()
                con.close()
            if r:
                return {"email": r[0], "exp": r[1]}
            return None
        except Exception:
            pass
    return _file_get("sessions", token)


def _del_session(token: str) -> None:
    con = _pg()
    if con is not None:
        try:
            cur = con.cursor()
            try:
                cur.execute("DELETE FROM genesis_sessions WHERE token = %s", (token,))
                con.commit()
            finally:
                cur.close()
                con.close()
        except Exception:
            pass
    _file_del("sessions", token)


# ---------- public API

def request_otp(email: str, mailer=None) -> None:
    email = str(email or "").strip().lower()[:120]
    if not valid_email(email):
        raise AuthFail(400, "valid email required")
    existing = _load_otp(email) or {"count": 0, "window_start": 0, "tries": 0}
    if _now() - int(existing.get("window_start") or 0) > REQ_WINDOW:
        existing = {"count": 0, "window_start": _now(), "tries": 0}
    if int(existing.get("count") or 0) >= REQ_LIMIT:
        raise AuthFail(429, "too many codes — try again in a few minutes")
    code = _new_otp()
    rec = {"hash": _otp_hash(code), "exp": _now() + OTP_TTL, "tries": 0,
           "count": int(existing.get("count") or 0) + 1,
           "window_start": int(existing.get("window_start") or _now())}
    _store_otp(email, rec)
    try:
        send_otp_mail(email, code, mailer)
    except AuthFail:
        _clear_otp(email)
        raise


def verify_otp(email: str, code: str, name=None):
    email = str(email or "").strip().lower()[:120]
    if not valid_email(email) or not code:
        raise AuthFail(400, "email and code required")
    rec = _load_otp(email)
    if not rec:
        raise AuthFail(401, "no code requested — ask for one first")
    if _now() > int(rec.get("exp") or 0):
        _clear_otp(email)
        raise AuthFail(401, "code expired — request a new one")
    tries = int(rec.get("tries") or 0)
    if tries >= OTP_TRIES:
        _clear_otp(email)
        raise AuthFail(401, "too many tries — request a new code")
    if not hmac.compare_digest(str(rec.get("hash") or ""),
                               _otp_hash(str(code).strip())):
        rec["tries"] = tries + 1
        _store_otp(email, rec)
        raise AuthFail(401, "wrong code")
    _clear_otp(email)
    member = _get_user(email)
    is_new = not member
    if is_new:
        clean_name = str(name or "").strip()[:60]
        if not clean_name:
            # Code was correct — keep it valid so the retry only adds a name.
            _store_otp(email, {"hash": rec["hash"], "exp": rec["exp"],
                               "tries": 0, "count": 0,
                               "window_start": rec.get("window_start", _now())})
            raise NeedProfile()
        member = {"email": email, "name": clean_name,
                  "createdAt": _now(), "lastLogin": _now()}
    else:
        member["lastLogin"] = _now()
    _save_user(member)
    token = secrets.token_urlsafe(32)
    _save_session(token, email, _now() + SESSION_TTL)
    return {"token": token,
            "member": {"email": member["email"], "name": member["name"]},
            "new": is_new}


def member_from_token(token: str):
    token = str(token or "")
    if len(token) < 32:
        return None
    try:
        s = _load_session(token)
    except Exception:
        return None
    if not s or int(s.get("exp") or 0) < _now():
        return None
    try:
        u = _get_user(str(s.get("email") or "").lower())
    except Exception:
        return None
    if not u:
        return None
    return {"email": u["email"], "name": u.get("name", "")}


def logout(token: str) -> None:
    if token:
        _del_session(str(token))
