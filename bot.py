import html
import threading
import time
import sqlite3

import requests

import core
from core import connect, status, create_user, active_links, sub_url, fmt_gb, BRAND

API = "https://api.telegram.org/bot{}/{}"

BTN_CONFIGS = "📦 کانفیگ‌ها"
BTN_USAGE = "📊 مصرف من"
BTN_SUB = "🔗 لینک اشتراک"
KEYBOARD = {
    "keyboard": [[{"text": BTN_CONFIGS}, {"text": BTN_USAGE}], [{"text": BTN_SUB}]],
    "resize_keyboard": True,
}


def call(token, method, **params):
    try:
        return requests.post(API.format(token, method), json=params, timeout=45).json()
    except Exception as e:  # noqa: BLE001
        print(f"[bot] {method} error: {e}", flush=True)
        return None


def send(token, chat_id, text, keyboard=True):
    p = {"chat_id": chat_id, "text": text, "parse_mode": "HTML",
         "disable_web_page_preview": True}
    if keyboard:
        p["reply_markup"] = KEYBOARD
    call(token, "sendMessage", **p)


def usage_text(u):
    st = status(u)
    if st["quota"] > 0:
        vol = f"مصرف: {fmt_gb(st['used'])} از {fmt_gb(st['quota'])} گیگ (مانده: {fmt_gb(st['remaining'])} گیگ)"
    else:
        vol = f"مصرف: {fmt_gb(st['used'])} گیگ (حجم نامحدود)"
    if st["days_left"] is None:
        days = "زمان: نامحدود"
    elif st["days_left"] < 0:
        days = "زمان: منقضی شده"
    else:
        days = f"زمان: {st['days_left']} روز مانده"
    return f"وضعیت: {st['label']}\n{vol}\n{days}"


def handle(token, msg):
    chat_id = msg["chat"]["id"]
    tg_id = msg["from"]["id"]
    text = (msg.get("text") or "").strip()
    conn = connect()
    try:
        u = conn.execute("SELECT * FROM users WHERE telegram_id=?", (tg_id,)).fetchone()

        if text.startswith("/start"):
            parts = text.split(maxsplit=1)
            code = parts[1].strip() if len(parts) > 1 else ""
            if code and not u:
                target = conn.execute("SELECT * FROM users WHERE token=?", (code,)).fetchone()
                if target and target["telegram_id"] is None:
                    conn.execute("UPDATE users SET telegram_id=? WHERE id=?", (tg_id, target["id"]))
                    conn.commit()
                    u = conn.execute("SELECT * FROM users WHERE id=?", (target["id"],)).fetchone()
                else:
                    send(token, chat_id, "این کد نامعتبره یا قبلاً به یه حساب دیگه وصل شده.", keyboard=False)
                    return
            if not u and core.SELF_SIGNUP:
                name = msg["from"].get("first_name") or "کاربر"
                u = create_user(conn, name, telegram_id=tg_id)
            if not u:
                send(token, chat_id,
                     "حسابی برای تو پیدا نشد. کد اتصال رو از ادمین بگیر و به‌شکل «/start کد» بفرست.",
                     keyboard=False)
                return
            send(token, chat_id, f"سلام {html.escape(u['name'])} 👋\nبه {html.escape(BRAND)} خوش اومدی.\n\n{usage_text(u)}")
            return

        if not u:
            send(token, chat_id, "اول /start رو بزن.", keyboard=False)
            return

        if text in (BTN_CONFIGS, "/configs"):
            st = status(u)
            if not st["ok"]:
                send(token, chat_id, f"اشتراکت الان {st['label']} هست، برای همین کانفیگی نمایش داده نمی‌شه.")
                return
            links = active_links(conn)
            if not links:
                send(token, chat_id, "فعلاً کانفیگی اضافه نشده.")
                return
            for l in links:
                send(token, chat_id, f"<code>{html.escape(l)}</code>")
        elif text in (BTN_USAGE, "/usage"):
            send(token, chat_id, usage_text(u))
        elif text in (BTN_SUB, "/sub"):
            url = sub_url(u["token"])
            if url.startswith("/"):
                send(token, chat_id, "آدرس عمومی سرویس هنوز تنظیم نشده (PUBLIC_URL).")
            else:
                send(token, chat_id, f"لینک اشتراک تو:\n<code>{html.escape(url)}</code>\n\nاینو توی برنامه‌ی کلاینت‌ات وارد کن.")
        else:
            send(token, chat_id, "از دکمه‌های پایین استفاده کن.")
    finally:
        conn.close()


def loop(token):
    me = call(token, "getMe")
    if me and me.get("ok"):
        core.BOT_USERNAME = me["result"].get("username", "")
        print(f"[bot] running as @{core.BOT_USERNAME}", flush=True)
    else:
        print("[bot] getMe failed; check TELEGRAM_BOT_TOKEN", flush=True)
    offset = 0
    while True:
        res = call(token, "getUpdates", offset=offset, timeout=30)
        if not res or not res.get("ok"):
            time.sleep(5)
            continue
        for upd in res["result"]:
            offset = upd["update_id"] + 1
            msg = upd.get("message")
            if not msg or msg.get("chat", {}).get("type") != "private":
                continue
            try:
                handle(token, msg)
            except Exception as e:  # noqa: BLE001
                print(f"[bot] handler error: {e}", flush=True)


_started = False


def start_bot(token):
    global _started
    if _started:
        return
    _started = True
    threading.Thread(target=loop, args=(token,), daemon=True).start()
