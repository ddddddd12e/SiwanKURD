import os
import sqlite3
import secrets
import base64
from datetime import date, timedelta
from urllib.parse import urlparse, unquote

BRAND = os.environ.get("BRAND_NAME", "SiwanKURD")
DB_PATH = os.environ.get("DB_PATH", "data.db")
DEFAULT_QUOTA_GB = float(os.environ.get("DEFAULT_QUOTA_GB", "5"))
DEFAULT_DAYS = int(os.environ.get("DEFAULT_DAYS", "30"))
SELF_SIGNUP = os.environ.get("BOT_SELF_SIGNUP", "1") == "1"
BOT_USERNAME = ""  # توسط ربات مقداردهی می‌شه

ALLOWED_SCHEMES = ("vless", "vmess", "trojan", "ss", "hysteria2", "hy2", "tuic")

SCHEMA = """
CREATE TABLE IF NOT EXISTS configs(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  label TEXT NOT NULL DEFAULT '',
  link TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  token TEXT NOT NULL UNIQUE,
  telegram_id INTEGER UNIQUE,
  quota_gb REAL NOT NULL DEFAULT 0,
  used_gb REAL NOT NULL DEFAULT 0,
  expires_at TEXT,
  enabled INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def connect():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    d = os.path.dirname(DB_PATH)
    if d:
        os.makedirs(d, exist_ok=True)
    conn = connect()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


def public_base():
    u = os.environ.get("PUBLIC_URL", "").rstrip("/")
    if u:
        return u
    d = os.environ.get("RAILWAY_PUBLIC_DOMAIN")
    return f"https://{d}" if d else ""


def sub_url(token):
    return f"{public_base()}/sub/{token}"


def fmt_gb(x):
    x = round(float(x or 0), 2)
    return str(int(x)) if x == int(x) else str(x)


def status(u):
    """وضعیت اشتراک یک کاربر."""
    quota = float(u["quota_gb"] or 0)
    used = float(u["used_gb"] or 0)
    days_left = None
    if u["expires_at"]:
        try:
            days_left = (date.fromisoformat(u["expires_at"]) - date.today()).days
        except ValueError:
            days_left = None
    pct = min(100, round(used / quota * 100)) if quota > 0 else 0
    if not u["enabled"]:
        state, label = "disabled", "غیرفعال"
    elif days_left is not None and days_left < 0:
        state, label = "expired", "منقضی شده"
    elif quota > 0 and used >= quota:
        state, label = "empty", "حجم تمام شده"
    else:
        state, label = "active", "فعال"
    return {
        "state": state,
        "label": label,
        "ok": state == "active",
        "days_left": days_left,
        "pct": pct,
        "quota": quota,
        "used": used,
        "remaining": max(quota - used, 0) if quota > 0 else None,
    }


def create_user(conn, name, quota_gb=None, days=None, telegram_id=None):
    quota_gb = DEFAULT_QUOTA_GB if quota_gb is None else quota_gb
    days = DEFAULT_DAYS if days is None else days
    expires = (date.today() + timedelta(days=days)).isoformat() if days and days > 0 else None
    token = secrets.token_urlsafe(16)
    conn.execute(
        "INSERT INTO users(name, token, telegram_id, quota_gb, expires_at) VALUES(?,?,?,?,?)",
        (name.strip()[:60] or "کاربر", token, telegram_id, quota_gb, expires),
    )
    conn.commit()
    return conn.execute("SELECT * FROM users WHERE token=?", (token,)).fetchone()


def parse_link(line):
    """یه لینک کانفیگ رو بررسی می‌کنه و (label, link) برمی‌گردونه؛ اگه نامعتبر بود None."""
    line = line.strip()
    if not line or "://" not in line:
        return None
    p = urlparse(line)
    if p.scheme.lower() not in ALLOWED_SCHEMES:
        return None
    label = unquote(p.fragment) if p.fragment else p.scheme.lower()
    return label[:80], line


def active_links(conn):
    return [r["link"] for r in conn.execute("SELECT link FROM configs WHERE active=1 ORDER BY id")]


def raw_subscription(links):
    return base64.b64encode("\n".join(links).encode()).decode()
