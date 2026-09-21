# SiwanKURD app v2 (works with flat or templates/static layout)
import os
import time
import hmac
import base64
import secrets
from datetime import date, datetime, timedelta
from functools import wraps

from jinja2 import ChoiceLoader, FileSystemLoader
from flask import (Flask, request, session, redirect, url_for, render_template,
                   abort, Response, flash, g, send_from_directory)

import core
from core import (connect, init_db, status, create_user, parse_link, active_links,
                  raw_subscription, sub_url, fmt_gb, BRAND)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# ساختار تخت: همه‌ی فایل‌ها کنار هم هستن (بدون پوشه)، تا آپلود از گوشی راحت باشه.
app = Flask(__name__, static_folder=None)
# قالب‌ها و فایل‌های استاتیک هم کنار app.py پیدا می‌شن، هم داخل پوشه‌های templates/static
SEARCH_DIRS = [BASE_DIR, os.path.join(BASE_DIR, "templates"), os.path.join(BASE_DIR, "static")]
app.jinja_loader = ChoiceLoader([FileSystemLoader(d) for d in SEARCH_DIRS])
STATIC_FILES = {"style.css", "app.js", "bg.jpg", "logo.webp"}


@app.route("/static/<path:filename>", endpoint="static")
def static_files(filename):
    if filename not in STATIC_FILES:  # فقط همین چهار فایل عمومی هستن
        abort(404)
    for d in SEARCH_DIRS:
        if os.path.isfile(os.path.join(d, filename)):
            return send_from_directory(d, filename, max_age=3600)
    abort(404)


app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=bool(os.environ.get("RAILWAY_PUBLIC_DOMAIN")),
    PERMANENT_SESSION_LIFETIME=timedelta(days=7),
)

ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASS")
if not ADMIN_PASS:
    ADMIN_PASS = secrets.token_urlsafe(9)
    print(f"[!] ADMIN_PASS تنظیم نشده. رمز موقت ادمین: {ADMIN_PASS}", flush=True)

init_db()

if os.environ.get("TELEGRAM_BOT_TOKEN"):
    from bot import start_bot
    start_bot(os.environ["TELEGRAM_BOT_TOKEN"])

CLIENT_UAS = ("v2ray", "clash", "hiddify", "streisand", "sing-box", "singbox",
              "shadowrocket", "v2box", "happ", "nekoray", "nekobox", "foxray")

_FA = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


@app.template_filter("fa")
def fa(v):
    return str(v).translate(_FA)


@app.template_filter("gb")
def gb(v):
    return fmt_gb(v)


def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    return session["csrf"]


@app.context_processor
def inject():
    return {"brand": BRAND, "csrf_token": csrf_token, "core": core}


def db():
    if "db" not in g:
        g.db = connect()
    return g.db


@app.teardown_appcontext
def close_db(_):
    d = g.pop("db", None)
    if d:
        d.close()


@app.before_request
def csrf_protect():
    if request.method == "POST" and request.path.startswith("/admin"):
        if not hmac.compare_digest(request.form.get("csrf", ""), session.get("csrf", "")):
            abort(400)


def login_required(f):
    @wraps(f)
    def w(*a, **kw):
        if not session.get("admin"):
            return redirect(url_for("login"))
        return f(*a, **kw)
    return w


def num(v, default=0.0):
    try:
        return max(float(str(v).replace("٫", ".").strip()), 0.0)
    except ValueError:
        return default


_attempts = {}


def client_ip():
    return (request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or request.remote_addr or "?")


def too_many(ip):
    now = time.time()
    lst = [t for t in _attempts.get(ip, []) if now - t < 600]
    _attempts[ip] = lst
    return len(lst) >= 10


@app.route("/healthz")
def healthz():
    return "ok"


@app.route("/")
def index():
    return redirect(url_for("admin"))


@app.route("/admin/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        ip = client_ip()
        if too_many(ip):
            flash("تعداد تلاش‌ها زیاد بود. ۱۰ دقیقه بعد دوباره امتحان کن.", "bad")
        else:
            u_ok = hmac.compare_digest(request.form.get("username", ""), ADMIN_USER)
            p_ok = hmac.compare_digest(request.form.get("password", ""), ADMIN_PASS)
            if u_ok and p_ok:
                session.clear()
                session["admin"] = True
                session.permanent = True
                return redirect(url_for("admin"))
            _attempts.setdefault(ip, []).append(time.time())
            flash("نام کاربری یا رمز اشتباهه.", "bad")
    return render_template("login.html")


@app.route("/admin/logout", methods=["POST"])
@login_required
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/admin")
@login_required
def admin():
    conn = db()
    users = [dict(u, st=status(u)) for u in conn.execute("SELECT * FROM users ORDER BY id DESC")]
    configs = conn.execute("SELECT * FROM configs ORDER BY id DESC").fetchall()
    stats = {
        "users": len(users),
        "active_users": sum(1 for u in users if u["st"]["ok"]),
        "configs": sum(1 for c in configs if c["active"]),
        "used": sum(u["used_gb"] for u in users),
    }
    return render_template("admin.html", users=users, configs=configs, stats=stats,
                           bot=core.BOT_USERNAME, sub_url=sub_url)


# ---------- کاربرها ----------
@app.route("/admin/users/add", methods=["POST"])
@login_required
def user_add():
    name = request.form.get("name", "").strip()
    if not name:
        flash("اسم کاربر رو وارد کن.", "bad")
        return redirect(url_for("admin"))
    create_user(db(), name, num(request.form.get("quota_gb"), core.DEFAULT_QUOTA_GB),
                int(num(request.form.get("days"), core.DEFAULT_DAYS)))
    flash(f"کاربر «{name}» ساخته شد.", "ok")
    return redirect(url_for("admin"))


@app.route("/admin/users/<int:uid>/update", methods=["POST"])
@login_required
def user_update(uid):
    exp = request.form.get("expires_at", "").strip()
    try:
        exp = date.fromisoformat(exp).isoformat() if exp else None
    except ValueError:
        flash("فرمت تاریخ درست نیست.", "bad")
        return redirect(url_for("admin"))
    db().execute("UPDATE users SET name=?, quota_gb=?, used_gb=?, expires_at=? WHERE id=?",
                 (request.form.get("name", "").strip()[:60] or "کاربر",
                  num(request.form.get("quota_gb")), num(request.form.get("used_gb")), exp, uid))
    db().commit()
    flash("تغییرات ذخیره شد.", "ok")
    return redirect(url_for("admin"))


@app.route("/admin/users/<int:uid>/toggle", methods=["POST"])
@login_required
def user_toggle(uid):
    db().execute("UPDATE users SET enabled = 1 - enabled WHERE id=?", (uid,))
    db().commit()
    return redirect(url_for("admin"))


@app.route("/admin/users/<int:uid>/newtoken", methods=["POST"])
@login_required
def user_newtoken(uid):
    db().execute("UPDATE users SET token=? WHERE id=?", (secrets.token_urlsafe(16), uid))
    db().commit()
    flash("لینک اشتراک جدید ساخته شد؛ لینک قبلی دیگه کار نمی‌کنه.", "ok")
    return redirect(url_for("admin"))


@app.route("/admin/users/<int:uid>/delete", methods=["POST"])
@login_required
def user_delete(uid):
    db().execute("DELETE FROM users WHERE id=?", (uid,))
    db().commit()
    flash("کاربر حذف شد.", "ok")
    return redirect(url_for("admin"))


# ---------- کانفیگ‌ها ----------
@app.route("/admin/configs/add", methods=["POST"])
@login_required
def config_add():
    added = skipped = 0
    existing = {r["link"] for r in db().execute("SELECT link FROM configs")}
    for line in request.form.get("links", "").splitlines():
        if not line.strip():
            continue
        parsed = parse_link(line)
        if not parsed or parsed[1] in existing:
            skipped += 1
            continue
        db().execute("INSERT INTO configs(label, link) VALUES(?,?)", parsed)
        existing.add(parsed[1])
        added += 1
    db().commit()
    if added:
        flash(f"{added} کانفیگ اضافه شد." + (f" ({skipped} مورد نامعتبر یا تکراری بود)" if skipped else ""), "ok")
    else:
        flash("لینک معتبری پیدا نشد. هر خط باید با vless:// ، vmess:// ، trojan:// یا ss:// شروع بشه.", "bad")
    return redirect(url_for("admin"))


@app.route("/admin/configs/<int:cid>/toggle", methods=["POST"])
@login_required
def config_toggle(cid):
    db().execute("UPDATE configs SET active = 1 - active WHERE id=?", (cid,))
    db().commit()
    return redirect(url_for("admin"))


@app.route("/admin/configs/<int:cid>/delete", methods=["POST"])
@login_required
def config_delete(cid):
    db().execute("DELETE FROM configs WHERE id=?", (cid,))
    db().commit()
    return redirect(url_for("admin"))


# ---------- صفحه‌ی اشتراک کاربر ----------
def _b64(s):
    return base64.b64encode(s.encode()).decode()


@app.route("/sub/<token>")
def sub(token):
    u = db().execute("SELECT * FROM users WHERE token=?", (token,)).fetchone()
    if not u:
        abort(404)
    st = status(u)
    links = active_links(db()) if st["ok"] else []
    ua = request.headers.get("User-Agent", "").lower()
    if request.args.get("raw") == "1" or any(k in ua for k in CLIENT_UAS):
        expire = 0
        if u["expires_at"]:
            expire = int(datetime.combine(date.fromisoformat(u["expires_at"]),
                                          datetime.min.time()).timestamp())
        headers = {
            "Content-Type": "text/plain; charset=utf-8",
            "Subscription-Userinfo": (f"upload=0; download={int(st['used'] * 1024 ** 3)}; "
                                      f"total={int(st['quota'] * 1024 ** 3)}; expire={expire}"),
            "Profile-Title": "base64:" + _b64(BRAND),
            "Profile-Update-Interval": "12",
        }
        return Response(raw_subscription(links), headers=headers)
    configs = [{"label": (parse_link(l) or ("", ""))[0] or "کانفیگ", "link": l} for l in links]
    return render_template("sub.html", u=u, st=st, configs=configs, url=sub_url(token) or request.url)


@app.errorhandler(404)
def not_found(_):
    return render_template("error.html", title="پیدا نشد",
                           msg="این آدرس وجود نداره یا لینک اشتراک عوض شده."), 404


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
