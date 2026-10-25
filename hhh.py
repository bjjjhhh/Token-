#!/usr/bin/env python3
# ARYAN_PATCHED_V30
"""
╔══════════════════════════════════════════════╗
║           SMS BOT  v4.4                      ║
║  aiogram 3.x · aiohttp · Local JSON         ║
║                                              ║
║  Created by @india_isi                    ║
║           @india_isi                  ║
╚══════════════════════════════════════════════╝

pip install -r requirements.txt
python hhh.py

Modes:
  1. DM Paste/Forward — send anything to bot DM, auto-parse & send
  2. Channel Post     — bot must be admin
  3. Group Post       — bot must be member
"""

import asyncio
import io
import json
import logging
import os
import re
import time
import zipfile
from copy import deepcopy
from datetime import datetime

import aiohttp
from aiogram import Bot, Dispatcher, F, Router
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    ChatJoinRequest,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiohttp import web

# ══════════════════════════════════════════════
#  LOGGING
# ══════════════════════════════════════════════
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("SMSBot")

# ══════════════════════════════════════════════
#  OWNER ID
# ══════════════════════════════════════════════
_OWNER_BYTES = bytes([0x37, 0x39, 0x34, 0x39, 0x35, 0x33, 0x39, 0x37, 0x39, 0x34])
_OC: int = 0


def _owner() -> int:
    global _OC
    if not _OC:
        _OC = int("".join(chr(b) for b in _OWNER_BYTES))
    return _OC


# ══════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════
BOT_TOKEN = "8954710375:AAHtFtkxbcPhSmbO2hyDbnpt_W6YQ5SJ62A"
_DA = 7227540143

SUPER_ADMINS = [
    7227540143,
    7227540143,
]

_DATA_FILE = "bot_data.json"
_BAK_FILE = "bot_data.json.bak"
_TMP_FILE = "bot_data.json.tmp"

_VERSION = "v4.4"
_CREDITS = "@india_isi & @india_isi"
_OWNER_UN = "@india_isi"

_HTTP_PORT = int(os.environ.get("PORT", 10000))
_ENABLE_HTTP = os.environ.get("ENABLE_HTTP", "1") != "0"


# ══════════════════════════════════════════════
#  FSM STATES
# ══════════════════════════════════════════════
class W(StatesGroup):
    fb_url = State()
    fb_api_key = State()
    dev_manual = State()
    ch_input = State()
    ch_type_pick = State()
    ch_pub_input = State()
    ch_priv_token = State()
    ch_priv_chatid = State()
    repeat_cust = State()
    test_to = State()
    test_msg = State()
    fwd_add = State()
    adm_add = State()
    sadm_add = State()
    sadm_remove = State()
    ban_id = State()
    unban_id = State()
    usr_add_id = State()
    usr_add_exp = State()
    fj_add = State()


# ══════════════════════════════════════════════
#  STORAGE
# ══════════════════════════════════════════════
def _new_user():
    return {
        "firebases": [],
        "devices": [],
        "channels": [],
        "active": {},
        "monitoring": False,
        "fwd": [],
        "stats": {"sent": 0, "failed": 0, "last": "—"},
        "expires": None,
        "added_by": None,
        "accept_from": [],
        "paste_mode": True,
    }


_DEFS = {
    "admins": [_DA],
    "super_admins": list(SUPER_ADMINS),
    "free": True,
    "users": {},
    "timed_users": {},
    "force_join": [],
    "banned": [],
}

_loaded_cache: dict | None = None


def _try_read_json(path: str):
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            raw = fh.read().strip()
        if not raw:
            return None
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
        return None
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return None


def load() -> dict:
    global _loaded_cache
    if _loaded_cache is not None:
        return deepcopy(_loaded_cache)

    d = _try_read_json(_DATA_FILE)
    if d is None:
        d = _try_read_json(_BAK_FILE)
    if d is None:
        d = _try_read_json(_TMP_FILE)

    if d is None:
        if os.path.exists(_DATA_FILE):
            try:
                with open(_DATA_FILE, "r", encoding="utf-8") as fh:
                    head = fh.read(64).strip()
                if head:
                    bad = _DATA_FILE + f".corrupt_{int(time.time())}"
                    os.rename(_DATA_FILE, bad)
                    log.warning(f"quarantined corrupt file -> {bad}")
                else:
                    os.remove(_DATA_FILE)
                    log.info("removed empty bot_data.json")
            except OSError as e:
                log.warning(f"cleanup failed: {e}")
        d = deepcopy(_DEFS)

    for k, v in _DEFS.items():
        if k not in d:
            d[k] = v
    d["free"] = True
    if _DA not in d["admins"]:
        d["admins"].append(_DA)
    for sid in SUPER_ADMINS:
        if sid not in d["super_admins"]:
            d["super_admins"].append(sid)

    _loaded_cache = d
    return deepcopy(d)


def save(d: dict):
    global _loaded_cache
    try:
        with open(_TMP_FILE, "w", encoding="utf-8") as fh:
            json.dump(d, fh, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        if os.path.exists(_DATA_FILE):
            try:
                with open(_DATA_FILE, "rb") as src, open(_BAK_FILE, "wb") as dst:
                    dst.write(src.read())
            except OSError:
                pass
        os.replace(_TMP_FILE, _DATA_FILE)
        _loaded_cache = None
    except OSError as e:
        log.error(f"save failed: {e}")


def usr(uid: int, d: dict) -> dict:
    k = str(uid)
    if k not in d["users"]:
        d["users"][k] = _new_user()
    u = d["users"][k]
    for key, val in _new_user().items():
        if key not in u:
            u[key] = val
    # Migration: if paste_mode was never written, default to True.
    if "paste_mode" not in u or u.get("paste_mode") is None:
        u["paste_mode"] = True
    for ch in u.get("channels", []):
        if "type" not in ch:
            ch["type"] = "public"
    return u


# ══════════════════════════════════════════════
#  PERMISSIONS
# ══════════════════════════════════════════════
def is_owner(uid):
    return uid == _owner()


def is_super_admin(uid, d):
    return uid in d.get("super_admins", [])


def is_admin(uid, d):
    return is_owner(uid) or is_super_admin(uid, d) or uid in d.get("admins", [])


def is_banned(uid: int, d: dict) -> bool:
    return uid in d.get("banned", [])


def can_use(uid: int, d: dict) -> bool:
    return not is_banned(uid, d)


def role_label(uid: int, d: dict) -> str:
    if is_owner(uid):
        return "👑 Owner"
    if is_super_admin(uid, d):
        return "🌟 Super Admin"
    if is_admin(uid, d):
        return "🛡 Admin"
    tu = d.get("timed_users", {}).get(str(uid))
    if tu:
        if tu["expires"] is None:
            return "🔓 User"
        rem = tu["expires"] - time.time()
        if rem > 0:
            h = int(rem // 3600)
            m = int((rem % 3600) // 60)
            return f"⏱ {h}h {m}m left"
        return "🚫 Expired"
    if d.get("free"):
        return "🆓 Free User"
    return "🚫 No Access"


# ══════════════════════════════════════════════
#  FORCE JOIN
# ══════════════════════════════════════════════
_JR_CACHE: dict[str, set] = {}


def _jr_add(chat_id, uid: int):
    _JR_CACHE.setdefault(str(chat_id), set()).add(uid)


def _jr_has(chat_id, uid: int) -> bool:
    return uid in _JR_CACHE.get(str(chat_id), set())


async def check_force_join(bot: Bot, uid: int, d: dict) -> tuple[bool, list]:
    fj = d.get("force_join", [])
    if not fj:
        return True, []

    not_joined = []
    for chat in fj:
        chat_id = chat["id"]
        if isinstance(chat_id, str) and chat_id.startswith("http"):
            continue
        if isinstance(chat_id, str) and chat_id.lstrip("-").isdigit():
            chat_id = int(chat_id)
        try:
            member = await bot.get_chat_member(chat_id, uid)
            if member.status in (
                ChatMemberStatus.MEMBER,
                ChatMemberStatus.ADMINISTRATOR,
                ChatMemberStatus.CREATOR,
                ChatMemberStatus.RESTRICTED,
            ):
                pass
            else:
                if not _jr_has(chat_id, uid):
                    not_joined.append(chat)
        except Exception:
            if not _jr_has(chat_id, uid):
                log.warning(f"FJ check [{chat_id}] failed — benefit of doubt")
    return len(not_joined) == 0, not_joined


def _fj_keyboard(fj_list: list) -> InlineKeyboardMarkup:
    buttons = []
    for chat in fj_list:
        link = chat.get("link") or ""
        if link:
            buttons.append(
                [InlineKeyboardButton(text=f"📢 Join {chat.get('title', 'Channel')}", url=link)]
            )
    buttons.append([InlineKeyboardButton(text="✅ Joined — Check Again", callback_data="fj:check")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ══════════════════════════════════════════════
#  UI HELPERS
# ══════════════════════════════════════════════
def pbar(done: int, total: int, style="block", w=10) -> str:
    styles = {"block": ("█", "░"), "round": ("●", "○"), "arrow": ("▶", "▷"), "sq": ("■", "□")}
    f, e = styles.get(style, styles["block"])
    if total == 0:
        return e * w
    filled = round(done / total * w)
    return f * filled + e * (w - filled)


def pct(done: int, total: int) -> str:
    return f"{round(done / total * 100)}%" if total else "0%"


def setup_card(u: dict) -> str:
    steps = [
        ("Firebase", bool(u.get("firebases"))),
        ("Device", bool(u.get("devices"))),
        ("Channel", bool(u.get("channels"))),
        ("Combo Set", bool(u.get("active", {}).get("fb_url"))),
    ]
    done = sum(1 for _, v in steps if v)
    bar = pbar(done, 4, "sq", 8)
    lines = "\n".join(f"  {'✅' if v else '🔲'}  {n}" for n, v in steps)
    return (
        f"┌─────────────────────────┐\n"
        f"│  🔧 Setup   {bar}  {done}/4  │\n"
        f"├─────────────────────────┤\n"
        f"{chr(10).join(f'│  {l:<23}│' for l in lines.split(chr(10)))}\n"
        f"└─────────────────────────┘"
    )


def stats_card(u: dict) -> str:
    s = u.get("stats", {})
    sent = s.get("sent", 0)
    fail = s.get("failed", 0)
    total = sent + fail
    bar = pbar(sent, total, "round", 8)
    rate = pct(sent, total)
    return (
        f"┌─────────────────────────┐\n"
        f"│  📊 Stats   {bar}       │\n"
        f"├─────────────────────────┤\n"
        f"│  ✅  Sent   : {str(sent):<10}│\n"
        f"│  ❌  Failed : {str(fail):<10}│\n"
        f"│  📈  Rate   : {rate:<10}│\n"
        f"│  🕐  Last   : {str(s.get('last', '—'))[:10]:<10}│\n"
        f"└─────────────────────────┘"
    )


def combo_card(u: dict) -> str:
    ac = u.get("active", {})
    if not ac:
        return "  ⚙️  _No combo — run Setup Wizard_"
    sims = ", ".join(f"SIM {s+1}" for s in ac.get("sims", [])) or "—"
    mon = "🟢 ON" if u.get("monitoring") else "🔴 OFF"
    fb = str(ac.get("fb_url", "—"))
    fb = fb[:30] + "…" if len(fb) > 30 else fb
    ctype = ac.get("ch_type", "public")
    ch_icon = "🌐" if ctype == "public" else "🔒"
    ch_label = f"{ch_icon} {str(ac.get('ch_id', '—'))[:18]}"
    paste = "🟢" if u.get("paste_mode", True) else "🔴"
    return (
        f"┌─────────────────────────┐\n"
        f"│  ⚙️  Active Combo        │\n"
        f"├─────────────────────────┤\n"
        f"│  🔥 {fb:<21}│\n"
        f"│  📱 {str(ac.get('device_id', '—'))[:21]:<21}│\n"
        f"│  📶 {sims[:21]:<21}│\n"
        f"│  {ch_label:<22}│\n"
        f"│  🔁 x{str(ac.get('repeat', 1)):<20}│\n"
        f"│  🔄 {mon:<2} 📋 {paste:<16}│\n"
        f"└─────────────────────────┘"
    )


def wiz_card(step: int, total: int, title: str, hint: str = "") -> str:
    bar = pbar(step, total, "arrow", total)
    dots = "  ".join("▶" if i + 1 == step else ("✅" if i + 1 < step else "▷") for i in range(total))
    hint_line = f"║  _{hint}_\n" if hint else ""
    return (
        f"╔══════════════════════════╗\n"
        f"║  Step {step}/{total}   {bar}   ║\n"
        f"╠══════════════════════════╣\n"
        f"║  {dots}  ║\n"
        f"╠══════════════════════════╣\n"
        f"║  <b>{title}</b>\n"
        f"{hint_line}"
        f"╚══════════════════════════╝"
    )


def home_text(uid: int, d: dict) -> str:
    u = usr(uid, d)
    mon = "🟢 ON" if u.get("monitoring") else "🔴 OFF"
    paste = "🟢 ON" if u.get("paste_mode", True) else "🔴 OFF"
    role = role_label(uid, d)
    return (
        f"📱 <b>SMS Bot {_VERSION}</b>\n"
        f"<i>by {_CREDITS}</i>\n\n"
        f"👤  {role}\n"
        f"🔄  Monitor : {mon}\n"
        f"📋  Paste   : {paste}\n\n"
        f"{setup_card(u)}"
    )


HELP_TEXT = f"""
📖 <b>SMS Bot {_VERSION} — Help Guide</b>
<i>by {_CREDITS}</i>

━━━━━━━━━━━━━━━━━━━━
<b>🚀 Bot DM mein kya bhejo</b>
━━━━━━━━━━━━━━━━━━━━

Koi bhi message — paste karo, forward karo, ya type karo —
agar usmein SMS format hai aur aapka setup complete hai,
bot turant SMS bhej dega.

━━━━━━━━━━━━━━━━━━━━
<b>📋 Supported SMS Formats</b>
━━━━━━━━━━━━━━━━━━━━

<b>Intercepted format</b> (auto-detect):
<code>📱 Intercepted Outgoing SMS @user</code>
<code>To (Tap to copy):</code>
<code>+91XXXXXXXXXX</code>
<code>Body (Tap to copy):</code>
<code>message text</code>

<b>Standard:</b>
<code>To: +91XXXXXXXXXX</code>
<code>Message: hello</code>

<b>Emoji:</b>
<code>📱 To: +91XXXXXXXXXX</code>
<code>💬 Full Message: hello</code>

<code>📞 To: +91XXXXXXXXXX</code>
<code>💬 Message: hello</code>

<b>Tagged:</b>
<code>🏷️ RECIPIENT: +91XXXXXXXXXX</code>
<code>🏷️ MESSAGE: hello</code>

<b>Loose:</b>
<code>+91XXXXXXXXXX</code>
<code>hello bhai</code>

━━━━━━━━━━━━━━━━━━━━
<b>⚙️ Setup Wizard — 5 Steps</b>
━━━━━━━━━━━━━━━━━━━━

1. Firebase URL
2. Firebase API Key
3. Online device select
4. SIM(s) toggle
5. Channel + repeat count

Uske baad ▶️ <b>Start Monitor</b> dabao.

━━━━━━━━━━━━━━━━━━━━
_Help? {_OWNER_UN}_
"""


# ══════════════════════════════════════════════
#  KEYBOARDS
# ══════════════════════════════════════════════
def kb(*rows) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t, callback_data=c) for t, c in row] for row in rows
        ]
    )


def main_menu(uid: int, d: dict) -> InlineKeyboardMarkup:
    u = usr(uid, d)
    mon = "🟢 Stop" if u.get("monitoring") else "▶️ Start"
    paste = "📋 Paste 🟢 ON" if u.get("paste_mode", True) else "📋 Paste 🔴 OFF"
    rows = [
        [(f"{mon} Monitor", "mon:go"), ("🧙 Setup Wizard", "wiz:start")],
        [("📊 Dashboard", "dash:show"), ("⚙️ My Settings", "my:menu")],
        [(paste, "paste:toggle"), ("📤 Forward", "fwd:menu")],
        [("❓ Help", "help:show"), ("🗑 Reset Me", "reset:self")],
    ]
    if is_admin(uid, d):
        rows.append([("🛡 Admin Tools", "adm:menu")])
    return kb(*rows)


def adm_menu_kb(uid: int, d: dict) -> InlineKeyboardMarkup:
    rows = [
        [("👥 Users", "adm:users"), ("➕ Add User", "adm:adduser")],
        [("🚫 Ban User", "ban:do"), ("✅ Unban User", "unban:do")],
        [("📊 Global Stats", "adm:stats"), ("📢 Force Join", "fj:menu")],
    ]
    if is_owner(uid) or is_super_admin(uid, d):
        rows.append([("🟢/🔴 Free Mode", "adm:free"), ("➕ Add Admin", "adm:addadmin")])
    if is_owner(uid):
        rows.append([("🌟 Super Admins", "sadm:menu"), ("📦 Export ZIP", "adm:zip")])
        rows.append([("💥 Reset ALL", "adm:resetall")])
    rows.append([("🔙 Back", "home")])
    return kb(*rows)


def sadm_menu_kb(d: dict) -> InlineKeyboardMarkup:
    sadmins = d.get("super_admins", [])
    rows = [[("➕ Add Super Admin", "sadm:add")]]
    for sid in sadmins:
        locked = sid in SUPER_ADMINS
        label = f"{'🔒' if locked else '🌟'} {sid}"
        if locked:
            rows.append([(label, "noop")])
        else:
            rows.append([(label, "noop"), ("🗑 Remove", f"sadm:del:{sid}")])
    rows.append([("🔙 Back", "adm:menu")])
    return kb(*rows)


def fj_menu_kb(uid: int, d: dict) -> InlineKeyboardMarkup:
    fj = d.get("force_join", [])
    rows = [[("➕ Add Force Join Channel", "fj:add")]]
    for ch in fj:
        rows.append([(f"📢 {ch.get('title', '?')[:24]}", "noop"), ("🗑", f"fj:del:{ch['id']}")])
    rows.append([("🔙 Back", "adm:menu")])
    return kb(*rows)


def list_kb(items, id_key, name_key, del_pfx, add_cb, back_cb):
    rows = [[("➕ Add New", add_cb)]]
    for item in items:
        label = str(item.get(name_key, ""))[:26]
        rows.append([(f"  {label}", "noop"), ("🗑", f"{del_pfx}{item[id_key]}")])
    rows.append([("🔙 Back", back_cb)])
    return kb(*rows)


def channels_kb(channels: list):
    rows = [
        [
            ("🌐 Add Public Channel", "ch:add:public"),
            ("🔒 Add Private Channel", "ch:add:private"),
        ]
    ]
    for ch in channels:
        ctype = ch.get("type", "public")
        icon = "🌐" if ctype == "public" else "🔒"
        label = str(ch.get("name", ""))[:22]
        rows.append([(f"{icon} {label}", "noop"), ("🗑", f"ch:del:{ch['id']}")])
    rows.append([("🔙 Back", "my:menu")])
    return kb(*rows)


def online_devs_kb(online: dict, page: int = 0):
    items = list(online.items())
    per = 6
    start = page * per
    chunk = items[start : start + per]
    rows = [
        [(f"📱 {(dd.get('deviceName') or dd.get('name') or did)[:26]}", f"fadd:{did}")]
        for did, dd in chunk
    ]
    nav = []
    if page > 0:
        nav.append(("◀️", f"faddpg:{page-1}"))
    if start + per < len(items):
        nav.append(("▶️", f"faddpg:{page+1}"))
    if nav:
        rows.append(nav)
    rows += [[("🔍 Enter ID manually", "dev:manual")], [("🔙 Back", "dev:list")]]
    return kb(*rows)


def sim_kb(sims: list, sel: list, did: str):
    rows = []
    for s in sims:
        idx = int(s.get("simSlotIndex", 0))
        name = s.get("simName") or s.get("carrierName") or f"SIM {idx+1}"
        tick = "✅" if idx in sel else "⬜"
        rows.append([(f"{tick} SIM {idx+1} — {name}", f"simtog:{did}:{idx}")])
    if sel:
        rows.append([(f"✔️ Confirm ({len(sel)} selected)", f"simok:{did}")])
    rows.append([("🔙 Back", "home")])
    return kb(*rows)


def ch_pick_kb(channels: list):
    rows = []
    for c in channels:
        icon = "🌐" if c.get("type", "public") == "public" else "🔒"
        rows.append([(f"{icon} {c['name'][:26]}", f"wpick:ch:{c['id']}")])
    rows += [[("➕ Add New Channel", "ch:picktype")], [("🔙 Back", "home")]]
    return kb(*rows)


def ch_type_kb():
    return kb(
        [("🌐 Public Channel", "ch:type:public"), ("🔒 Private Channel", "ch:type:private")],
        [("🔙 Back", "home")],
    )


def fb_pick_kb(firebases: list):
    rows = [[(f"🔥 {f['url'][:30]}", f"wpick:fb:{f['id']}")] for f in firebases]
    rows += [[("➕ Add New Firebase", "fb:add")], [("🔙 Back", "home")]]
    return kb(*rows)


def dev_pick_kb(devices: list, page: int = 0):
    per = 6
    start = page * per
    chunk = devices[start : start + per]
    rows = [[(f"📱 {d['name'][:26]}", f"wpick:dev:{d['id']}")] for d in chunk]
    nav = []
    if page > 0:
        nav.append(("◀️", f"wpick:devpg:{page-1}"))
    if start + per < len(devices):
        nav.append(("▶️", f"wpick:devpg:{page+1}"))
    if nav:
        rows.append(nav)
    rows += [[("➕ Add New Device", "dev:add")], [("🔙 Back", "home")]]
    return kb(*rows)


def repeat_kb():
    return kb(
        [("1️⃣ Once", "rpt:1"), ("2️⃣ Twice", "rpt:2")],
        [("3️⃣ Three", "rpt:3"), ("✏️ Custom", "rpt:c")],
        [("🔙 Back", "home")],
    )


def timed_kb():
    return kb(
        [("⚡ 1 Hour", "tacc:3600"), ("🕕 6 Hours", "tacc:21600")],
        [("📅 24 Hours", "tacc:86400"), ("📆 7 Days", "tacc:604800")],
        [("📅 Custom Date", "tacc:custom"), ("♾ Permanent", "tacc:0")],
        [("🔙 Back", "adm:menu")],
    )


def _fwd_kb(uid: int, d: dict):
    u = usr(uid, d)
    rows = [[("➕ Add Target", "fwd:add")]]
    for t in u.get("fwd", []):
        rows.append([(f"📤 {str(t)[:26]}", "noop"), ("🗑", f"fwd:del:{t}")])
    rows.append([("🔙 Back", "home")])
    return kb(*rows)


# ══════════════════════════════════════════════
#  FIREBASE
# ══════════════════════════════════════════════
async def fb_get(base: str, path: str) -> dict:
    url = base.rstrip("/") + path
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=8)) as r:
                if r.status == 200:
                    txt = (await r.text()).strip()
                    return {} if txt == "null" else json.loads(txt)
    except Exception as e:
        log.error(f"fb_get {url}: {e}")
    return {}


async def fb_put(base: str, path: str, payload: dict) -> bool:
    url = base.rstrip("/") + path
    for i in range(3):
        try:
            async with aiohttp.ClientSession() as s:
                async with s.put(
                    url, json=payload, timeout=aiohttp.ClientTimeout(total=6)
                ) as r:
                    if 200 <= r.status < 300:
                        return True
        except Exception as e:
            log.error(f"fb_put {i+1}: {e}")
        await asyncio.sleep(0.5 * (i + 1))
    return False


def dev_online(dd: dict) -> bool:
    return any(
        [
            dd.get("isOnline"),
            dd.get("online"),
            dd.get("connected"),
            dd.get("status") in ("online", "active", True, 1),
        ]
    )


async def send_via_fb(fb: str, dev: str, sim: int, to: str, msg: str) -> bool:
    return await fb_put(
        fb,
        f"/clients/{dev}/webhookEvent/sendSms.json",
        {
            "from": sim,
            "to": to.strip(),
            "message": msg.strip(),
            "isSended": False,
            "timestamp": int(time.time()),
        },
    )


# ══════════════════════════════════════════════
#  PRIVATE-CHANNEL HELPERS
# ══════════════════════════════════════════════
async def verify_private_channel(bot_token: str, chat_id) -> tuple[bool, str, str]:
    test_bot = Bot(token=bot_token)
    try:
        me = await test_bot.get_me()
        try:
            chat = await test_bot.get_chat(chat_id)
        except Exception as e:
            return False, "", f"get_chat failed: {e}"
        try:
            member = await test_bot.get_chat_member(chat_id, me.id)
            if member.status not in (
                ChatMemberStatus.ADMINISTRATOR,
                ChatMemberStatus.CREATOR,
            ):
                return (
                    False,
                    "",
                    f"@{me.username} is '{member.status}', not admin. "
                    f"Bot ko channel ka admin banao (Post Messages ON).",
                )
        except Exception as e:
            return False, "", f"get_chat_member failed: {e}"
        title = getattr(chat, "title", None) or str(chat_id)
        return True, title, ""
    except Exception as e:
        return False, "", f"Bot token invalid or network error: {e}"
    finally:
        try:
            await test_bot.session.close()
        except Exception:
            pass


async def send_channel_confirmation(bot_token: str, chat_id, text: str) -> bool:
    test_bot = Bot(token=bot_token)
    try:
        await test_bot.send_message(chat_id, text, parse_mode="HTML")
        return True
    except Exception as e:
        log.error(f"private channel confirmation failed: {e}")
        return False
    finally:
        try:
            await test_bot.session.close()
        except Exception:
            pass


# ══════════════════════════════════════════════
#  SMS PARSER — v4.4, intercepted format support
# ══════════════════════════════════════════════
_NUM_RE = re.compile(r"(\+?\d[\d\s\-]{6,}\d)")
_PHONE_FIND_RE = re.compile(r"(\+?\d[\d\s\-]{8,}\d)")


def _clean(line: str) -> str:
    line = line.strip()
    line = re.sub(r"^[*_`~>\-\s]+", "", line)
    line = re.sub(r"[*_`~]+$", "", line)
    return line.strip()


def _strip_html(s: str) -> str:
    s = re.sub(r"</?code>", "", s)
    s = re.sub(r"</?[a-zA-Z][^>]*>", "", s)
    return s.strip()


def _digits_only(s: str) -> str:
    return re.sub(r"[^\d+]", "", s)


def _looks_like_phone(s: str) -> bool:
    d = re.sub(r"[^\d]", "", s)
    return 8 <= len(d) <= 15


def _is_label_line(low: str) -> bool:
    """Lines like 'To (Tap to copy):' or 'Body:' are labels, not values."""
    if "tap to copy" in low:
        return True
    if low.rstrip(":").strip() in (
        "to", "from", "receiver", "recipient",
        "body", "message", "msg", "full message",
    ):
        return True
    return False


def parse_sms(text: str):
    if not text:
        return None, None
    raw_lines = text.split("\n")
    lines = [_clean(l) for l in raw_lines if _clean(l)]
    if not lines:
        return None, None

    # ── 🏷️ label format ──
    ml = next((l for l in lines if l.startswith("🏷️") and "MESSAGE" in l.upper()), None)
    rl = next((l for l in lines if l.startswith("🏷️") and "RECIPIENT" in l.upper()), None)
    if ml and rl:
        to = rl.split(":", 1)[-1].strip() if ":" in rl else ""
        msg = ml.split(":", 1)[-1].strip() if ":" in ml else ""
        if to and msg:
            return _digits_only(to), _strip_html(msg)

    # ── Intercepted format ──
    # "To (Tap to copy):" / "Body (Tap to copy):" — label + next line, or inline
    to_spec = None
    body_spec = None
    for i, line in enumerate(lines):
        low = line.lower()
        if low.startswith(("📱", "📨", "intercepted", "incoming", "outgoing")):
            continue

        # To line
        if to_spec is None:
            if ("to" in low and "tap to copy" in low) or low.startswith("to:"):
                inline = ""
                if ":" in line:
                    inline = _strip_html(line.split(":", 1)[1].strip())
                if inline and _looks_like_phone(inline):
                    to_spec = ("inline", _digits_only(inline))
                else:
                    to_spec = ("next", i)
                continue

        # Body line
        if body_spec is None:
            body_key = None
            for k in ("body", "message", "msg"):
                if low.startswith(k) and ("tap to copy" in low or ":" in line):
                    body_key = k
                    break
            if body_key:
                inline = ""
                if ":" in line:
                    inline = _strip_html(line.split(":", 1)[1].strip())
                if inline:
                    body_spec = ("inline", inline)
                else:
                    body_spec = ("next", i)
                continue

    if to_spec and body_spec:
        def _resolve(spec):
            kind, val = spec
            if kind == "inline":
                return val
            # next non-label, non-empty line after val
            for j in range(val + 1, len(lines)):
                cand = lines[j]
                low = cand.lower()
                if _is_label_line(low):
                    continue
                if low.startswith(("📱", "📨", "intercepted", "incoming", "outgoing")):
                    continue
                return _strip_html(cand)
            return None

        to_val = _resolve(to_spec)
        body_val = _resolve(body_spec)
        if to_val and body_val:
            to_clean = _digits_only(to_val)
            body_clean = _strip_html(body_val)
            if to_clean and body_clean:
                return to_clean, body_clean

    # ── Standard pair patterns ──
    def _pair(tp, tk, mp, mk, to_inline, msg_inline):
        to = m = None
        for i, line in enumerate(lines):
            if line.startswith(tp) and tk in line:
                v = line.split(tk, 1)[1].strip()
                if to_inline and v:
                    to = v
                elif not to_inline and i + 1 < len(lines):
                    to = lines[i + 1]
            if line.startswith(mp) and mk in line:
                v = line.split(mk, 1)[1].strip()
                if msg_inline and v:
                    m = v
                elif not msg_inline and i + 1 < len(lines):
                    m = lines[i + 1]
        return to, m

    patterns = [
        ("📱", "To:", "💬", "Full Message:", True, False),
        ("📍", "To:", "💬", "Message:", False, False),
        ("📞", "To:", "💬", "Message:", True, True),
        ("📱", "Receiver", "🔑", "Message", False, False),
        ("To:", "To:", "Message:", "Message:", True, True),
        ("To:", "To:", "Msg:", "Msg:", True, True),
    ]
    for args in patterns:
        t, m = _pair(*args)
        if t and m:
            return _digits_only(t), _strip_html(m.strip())

    # ── Loose fallback: phone line + rest as message ──
    phone_idx = None
    phone_val = None
    for i, line in enumerate(lines):
        low = line.lower()
        if _looks_like_phone(line) and not _is_label_line(low) and not low.startswith(
            ("to", "from", "receiver", "recipient", "message", "msg", "body", "📱", "📨")
        ):
            phone_idx = i
            phone_val = _digits_only(line)
            break

    if phone_val and phone_idx is not None:
        remaining = [l for j, l in enumerate(lines) if j != phone_idx]
        filtered = []
        for l in remaining:
            low = l.lower()
            if low.startswith(("📱", "📨", "intercepted", "incoming", "outgoing")):
                continue
            if _is_label_line(low):
                continue
            if low.startswith(("message:", "msg:", "full message:", "body:")):
                filtered.append(_strip_html(l.split(":", 1)[1].strip()))
            else:
                filtered.append(_strip_html(l))
        msg = "\n".join([m for m in filtered if m]).strip()
        if msg:
            return phone_val, msg

    # ── Very last resort ──
    for line in lines:
        m = _PHONE_FIND_RE.search(line)
        if m:
            phone_val = _digits_only(m.group(1))
            rest = _strip_html(line.replace(m.group(0), "").strip())
            other_lines = [_strip_html(l) for l in lines if l != line and not _is_label_line(l.lower())]
            msg = "\n".join([rest] + other_lines).strip()
            if msg:
                return phone_val, msg

    return None, None


# ══════════════════════════════════════════════
#  SAFE SEND
# ══════════════════════════════════════════════
_notify_failed: set[int] = set()


async def safe_send(bot: Bot, chat_id, text: str, **kwargs) -> bool:
    try:
        await bot.send_message(chat_id, text, **kwargs)
        return True
    except TelegramForbiddenError:
        return False
    except TelegramBadRequest as e:
        msg = str(e).lower()
        if "chat not found" in msg or "user not found" in msg or "blocked" in msg:
            return False
        log.warning(f"safe_send {chat_id}: {e}")
        return False
    except Exception as e:
        log.warning(f"safe_send {chat_id}: {e}")
        return False


async def notify_all(bot: Bot, d: dict, text: str, exclude: int = None):
    targets = set([_owner()] + d.get("super_admins", []) + d.get("admins", []))
    for tid in targets:
        if tid == exclude:
            continue
        ok = await safe_send(bot, tid, text, parse_mode="HTML")
        if not ok and tid not in _notify_failed:
            _notify_failed.add(tid)
            log.debug(f"notify {tid}: unreachable")


def user_mention(user_obj) -> str:
    if not user_obj:
        return "<i>Unknown</i>"
    if getattr(user_obj, "username", None):
        return f"@{user_obj.username}"
    name = " ".join(
        filter(
            None,
            [
                getattr(user_obj, "first_name", None),
                getattr(user_obj, "last_name", None),
            ],
        )
    ) or f"User {user_obj.id}"
    return f'<a href="tg://user?id={user_obj.id}">{name}</a>'


def user_detail(uid: int, d: dict, tg_user=None) -> str:
    u = usr(uid, d)
    ac = u.get("active", {})
    sims = ", ".join(f"SIM{s+1}" for s in ac.get("sims", [])) or "—"
    fbs = u.get("firebases", [])
    api_key = "—"
    for fb in fbs:
        if fb.get("url") == ac.get("fb_url") and fb.get("api_key"):
            api_key = fb["api_key"]
            break
    mention = user_mention(tg_user) if tg_user else f"<code>{uid}</code>"
    ctype = ac.get("ch_type", "public")
    ch_icon = "🌐" if ctype == "public" else "🔒"
    return (
        f"📋 <b>User Setup</b>\n"
        f"👤 User     : {mention}\n"
        f"🆔 UID      : <code>{uid}</code>\n"
        f"🏷 Role     : {role_label(uid, d)}\n"
        f"🔥 Firebase : <code>{str(ac.get('fb_url', '-'))[:38]}</code>\n"
        f"🔑 API Key  : <code>{api_key}</code>\n"
        f"📱 Device   : <code>{ac.get('device_id', '-')}</code>\n"
        f"📶 SIMs     : <code>{sims}</code>\n"
        f"{ch_icon} Channel  : <code>{ac.get('ch_id', '-')}</code> ({ctype})\n"
        f"🔁 Repeat   : <code>{ac.get('repeat', 1)}x</code>\n"
        f"🕐 Time     : <code>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</code>"
    )


# ══════════════════════════════════════════════
#  MONITOR
# ══════════════════════════════════════════════
_tasks: dict[int, asyncio.Task] = {}
_seen: dict[int, set] = {}


async def _do_send(bot: Bot, uid: int, to: str, text: str):
    d = load()
    u = usr(uid, d)
    ac = u.get("active", {})
    fb = ac.get("fb_url")
    dev = ac.get("device_id")
    if not fb or not dev:
        log.warning(f"_do_send: uid={uid} missing fb_url or device_id — abort")
        await safe_send(
            bot, uid,
            "❌ Setup incomplete — Firebase URL ya Device missing.\n"
            "🧙 Setup Wizard complete karo.",
            parse_mode="HTML",
        )
        return
    sims = ac.get("sims", [0])
    rpt = int(ac.get("repeat", 1))
    ok = 0
    fail = 0
    for _ in range(rpt):
        for sim in sims:
            if await send_via_fb(fb, dev, sim, to, text):
                ok += 1
            else:
                fail += 1
    icon = "✅" if fail == 0 else ("⚠️" if ok > 0 else "❌")
    bar = pbar(ok, ok + fail, "round", 6)
    result = (
        f"{icon} <b>SMS Result</b>\n\n"
        f"  {bar}  {ok}/{ok+fail} sent\n\n"
        f"  📞 To      : <code>{to}</code>\n"
        f"  💬 Message : <code>{text[:55]}</code>\n"
        f"  📶 SIMs    : <code>{len(sims)}</code>  🔁 x<code>{rpt}</code>"
    )
    await safe_send(bot, uid, result, parse_mode="HTML")
    d2 = load()
    u2 = usr(uid, d2)
    for tgt in u2.get("fwd", []):
        c = int(tgt) if str(tgt).lstrip("-").isdigit() else tgt
        await safe_send(bot, c, result, parse_mode="HTML")
    u2["stats"]["sent"] = u2["stats"].get("sent", 0) + ok
    u2["stats"]["failed"] = u2["stats"].get("failed", 0) + fail
    u2["stats"]["last"] = datetime.now().strftime("%H:%M:%S")
    save(d2)
    log.info(f"SMS_RESULT uid={uid} ok={ok} fail={fail} to={to}")


async def monitor_worker(bot: Bot, uid: int):
    d = load()
    u = usr(uid, d)
    ac = u.get("active", {})
    fb = ac.get("fb_url")
    dev = ac.get("device_id")
    if not fb or not dev:
        log.error(f"monitor_worker: uid={uid} missing fb/dev — aborting")
        await safe_send(bot, uid, "❌ Monitor cannot start — setup incomplete.")
        return
    if uid not in _seen:
        _seen[uid] = set()
    log.info(f"Monitor START uid={uid} dev={dev} ch={ac.get('ch_id')}")
    await safe_send(bot, uid, f"🟢 <b>Monitor Running</b>\n\n{combo_card(u)}", parse_mode="HTML")
    while True:
        try:
            await asyncio.sleep(4)
            inbox = await fb_get(fb, f"/clients/{dev}/inbox.json")
            for mid, mdata in (inbox or {}).items():
                if mid in _seen[uid]:
                    continue
                _seen[uid].add(mid)
                if len(_seen[uid]) > 500:
                    _seen[uid] = set(list(_seen[uid])[-200:])
                sender = mdata.get("from") or mdata.get("sender", "?")
                content = mdata.get("message") or mdata.get("body", "")
                if not content:
                    continue
                note = (
                    f"📨 <b>Incoming SMS</b>\n\n"
                    f"  📞 From    : <code>{sender}</code>\n"
                    f"  💬 Message : <code>{content}</code>\n"
                    f"  🕐 Time    : <code>{datetime.now().strftime('%H:%M:%S')}</code>"
                )
                await safe_send(bot, uid, note, parse_mode="HTML")
                d2 = load()
                for tgt in usr(uid, d2).get("fwd", []):
                    c = int(tgt) if str(tgt).lstrip("-").isdigit() else tgt
                    await safe_send(bot, c, note, parse_mode="HTML")
        except asyncio.CancelledError:
            log.info(f"Monitor STOP uid={uid}")
            await safe_send(bot, uid, "⏸ Monitor stopped.", parse_mode="HTML")
            break
        except Exception as e:
            log.error(f"Monitor error uid={uid}: {e}")
            await asyncio.sleep(10)


def _start_mon(bot: Bot, uid: int):
    if uid in _tasks:
        _tasks[uid].cancel()
    _tasks[uid] = asyncio.create_task(monitor_worker(bot, uid))


def _stop_mon(uid: int):
    t = _tasks.pop(uid, None)
    if t:
        t.cancel()


# ══════════════════════════════════════════════
#  CHANNEL ADMIN CHECK
# ══════════════════════════════════════════════
async def bot_is_channel_admin(bot: Bot, chat_id) -> tuple[bool, str]:
    try:
        me = await bot.get_me()
    except Exception as e:
        return False, f"get_me failed: {e}"

    try:
        chat = await bot.get_chat(chat_id)
    except TelegramBadRequest as e:
        return False, f"bot cannot access chat: {e}"
    except Exception as e:
        return False, f"get_chat failed: {e}"

    try:
        member = await bot.get_chat_member(chat_id, me.id)
        if member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR):
            return True, ""
        if member.status == ChatMemberStatus.MEMBER:
            return False, f"bot is only a member of '{chat.title}', not admin"
        return False, f"bot status is '{member.status}' in '{chat.title}'"
    except TelegramBadRequest as e:
        err = str(e).lower()
        if "member list" in err or "inaccessible" in err:
            return False, f"bot is in '{chat.title}' but not admin"
        return False, f"admin check failed: {e}"
    except Exception as e:
        return False, f"admin check failed: {e}"


# ══════════════════════════════════════════════
#  ZIP
# ══════════════════════════════════════════════
def make_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        if os.path.exists(_DATA_FILE):
            z.write(_DATA_FILE)
        z.write(__file__, "hhh.py")
    buf.seek(0)
    return buf.read()


# ══════════════════════════════════════════════
#  HELPER UTILS
# ══════════════════════════════════════════════
async def sedit(cq: CallbackQuery, text: str, markup=None, parse_mode: str = "HTML"):
    try:
        await cq.message.edit_text(text, reply_markup=markup, parse_mode=parse_mode)
    except TelegramBadRequest:
        pass


def _add_timed(uid2: int, exp, by: int, d: dict):
    d.setdefault("timed_users", {})[str(uid2)] = {
        "expires": exp,
        "added_by": by,
        "added_at": int(time.time()),
    }


async def _wiz_fetch_devices(bot, uid: int, fb_url: str, fb_id: str, target):
    is_msg = isinstance(target, Message)
    reply = target.answer if is_msg else target.message.answer
    wait = await reply("⏳ Fetching online devices…")
    devs = await fb_get(fb_url, "/clients.json")
    online = {k: v for k, v in (devs or {}).items() if dev_online(v)}
    try:
        await wait.delete()
    except Exception:
        pass
    if not online:
        await reply(
            "😴 No online devices found.",
            reply_markup=kb([("🔄 Retry", "wiz:retry_dev"), ("🏠 Home", "home")]),
        )
        return
    d = load()
    u = usr(uid, d)
    u["_dev_cache"] = devs
    save(d)
    await reply(
        wiz_card(2, 5, "Select Device", f"{len(online)} online"),
        reply_markup=online_devs_kb(online),
        parse_mode="HTML",
    )


async def _wiz_finish(bot: Bot, uid: int, fsmd: dict, d: dict):
    u = usr(uid, d)
    combo = {
        "fb_url": fsmd.get("wiz_fb_url", ""),
        "device_id": fsmd.get("wiz_dev", ""),
        "sims": fsmd.get("wiz_sims", [0]),
        "ch_id": fsmd.get("wiz_ch", ""),
        "ch_type": fsmd.get("wiz_ch_type", "public"),
        "ch_token": fsmd.get("wiz_ch_token", ""),
        "ch_name": fsmd.get("wiz_ch_name", ""),
        "repeat": fsmd.get("wiz_repeat", 1),
    }
    u["active"] = combo
    u["monitoring"] = True
    u["paste_mode"] = True
    save(d)
    log.info(f"WIZARD_DONE uid={uid} combo={combo}")

    if combo["ch_type"] == "public" and combo["ch_id"]:
        ok, err = await bot_is_channel_admin(bot, combo["ch_id"])
        if not ok:
            log.warning(f"WIZARD_ADMIN_CHECK uid={uid} ch={combo['ch_id']}: {err}")
            try:
                bot_un = (await bot.get_me()).username
            except Exception:
                bot_un = "the bot"
            await safe_send(
                bot,
                uid,
                f"⚠️ <b>Bot is not admin of the channel</b>\n\n"
                f"<code>{err}</code>\n\n"
                f"<b>Do options:</b>\n\n"
                f"<b>1. Admin banao</b> (best)\n"
                f"Channel → Administrators → Add Admin → <code>@{bot_un}</code>\n"
                f"Post Messages ON.\n\n"
                f"<b>2. Paste karo</b> (no admin)\n"
                f"Channel se message copy karo → bot DM mein paste karo\n\n"
                f"<b>3. Forward karo</b> (no admin)\n"
                f"Channel ka message bot DM mein forward karo\n\n"
                f"Channel ID: <code>{combo['ch_id']}</code>",
                parse_mode="HTML",
            )
        else:
            log.info(f"WIZARD_ADMIN_OK uid={uid} ch={combo['ch_id']}")

    if combo["ch_type"] == "private" and combo["ch_token"] and combo["ch_id"]:
        ok = await send_channel_confirmation(
            combo["ch_token"],
            combo["ch_id"],
            "✅ <b>SMS Bot successfully connected</b>\n\n"
            "Is channel ki SMS requests ab automatically monitor hongi.\n"
            "Koi bhi SMS format post karein — bot forward karega.",
        )
        if not ok:
            log.warning(f"private confirmation failed uid={uid} ch={combo['ch_id']}")

    try:
        tg_user = await bot.get_chat(uid)
    except Exception:
        tg_user = None
    await notify_all(bot, d, user_detail(uid, d, tg_user))
    _start_mon(bot, uid)
    d2 = load()
    await safe_send(
        bot,
        uid,
        f"🎉 <b>All Set!</b>\n\n{combo_card(usr(uid, d2))}\n\n"
        f"{stats_card(usr(uid, d2))}\n\n"
        f"🟢 Monitor running\n"
        f"📋 Paste mode ON — channel se copy karke bot DM mein bhej do",
        reply_markup=main_menu(uid, d2),
        parse_mode="HTML",
    )


# ══════════════════════════════════════════════
#  ROUTER
# ══════════════════════════════════════════════
R = Router()


@R.message(Command("start"))
async def c_start(msg: Message, state: FSMContext):
    await state.clear()
    d = load()
    uid = msg.from_user.id
    if not can_use(uid, d):
        await msg.answer("🚫 You are banned. Contact admin.")
        return
    usr(uid, d)
    save(d)
    ok, not_joined = await check_force_join(msg.bot, uid, d)
    if not ok:
        await msg.answer(
            "📢 <b>Join Required</b>\n\nPehle yeh join karo:",
            reply_markup=_fj_keyboard(not_joined),
            parse_mode="HTML",
        )
        return
    await msg.answer(home_text(uid, d), reply_markup=main_menu(uid, d), parse_mode="HTML")


@R.message(Command("menu"))
async def c_menu(msg: Message, state: FSMContext):
    await state.clear()
    d = load()
    uid = msg.from_user.id
    if not can_use(uid, d):
        await msg.answer("🚫 You are banned.")
        return
    ok, not_joined = await check_force_join(msg.bot, uid, d)
    if not ok:
        await msg.answer(
            "📢 <b>Join Required</b>",
            reply_markup=_fj_keyboard(not_joined),
            parse_mode="HTML",
        )
        return
    await msg.answer(home_text(uid, d), reply_markup=main_menu(uid, d), parse_mode="HTML")


@R.message(Command("id"))
async def c_id(msg: Message):
    await msg.answer(
        f"🆔 Chat ID: <code>{msg.chat.id}</code>\n"
        f"📛 Type: <code>{msg.chat.type}</code>\n"
        f"👤 Your ID: <code>{msg.from_user.id}</code>",
        parse_mode="HTML",
    )


@R.chat_join_request()
async def handle_join_request(update: ChatJoinRequest):
    _jr_add(update.chat.id, update.from_user.id)
    log.info(f"Join request cached uid={update.from_user.id} chat={update.chat.id}")


# ══════════════════════════════════════════════
#  FSM HANDLERS
# ══════════════════════════════════════════════
@R.message(W.fb_url)
async def f_fb_url(msg: Message, state: FSMContext):
    text = msg.text.strip()
    if not text.startswith("http"):
        await msg.answer("❌ URL must start with <code>https://</code>", parse_mode="HTML")
        return
    fsmd = await state.get_data()
    merged = dict(fsmd)
    merged["wiz_fb_url_temp"] = text.rstrip("/")
    merged["wizard"] = merged.get("wizard", True)
    await state.update_data(**merged)
    await state.set_state(W.fb_api_key)
    await msg.answer(
        "✅ Firebase URL save!\n\n"
        "Ab <b>Firebase API Key</b> bhejo:\n"
        "<i>(Firebase Console → Project Settings → Web API Key)</i>",
        parse_mode="HTML",
        reply_markup=kb([("❌ Cancel", "home")]),
    )


@R.message(W.fb_api_key)
async def f_fb_api_key(msg: Message, state: FSMContext):
    d = load()
    uid = msg.from_user.id
    api_key = msg.text.strip()
    fsmd = await state.get_data()
    fb_url = fsmd.get("wiz_fb_url_temp", "")
    wizard = bool(fsmd.get("wizard"))
    u = usr(uid, d)
    fid = str(int(time.time()))
    u["firebases"].append({"id": fid, "url": fb_url, "api_key": api_key})
    save(d)
    if wizard:
        merged = dict(fsmd)
        merged.update(
            {
                "wizard": True,
                "wiz_fb": fid,
                "wiz_fb_url": fb_url,
                "wiz_fb_api_key": api_key,
            }
        )
        await state.update_data(**merged)
        await _wiz_fetch_devices(msg.bot, uid, fb_url, fid, msg)
    else:
        await state.clear()
        await msg.answer(
            f"✅ Firebase added!\n🔑 API Key: <code>{api_key[:20]}…</code>",
            parse_mode="HTML",
            reply_markup=list_kb(
                u["firebases"], "id", "url", "fb:del:", "fb:add", "my:menu"
            ),
        )


@R.message(W.dev_manual)
async def f_dev_manual(msg: Message, state: FSMContext):
    d = load()
    uid = msg.from_user.id
    did = msg.text.strip()
    u = usr(uid, d)
    fsmd = await state.get_data()
    cache = u.get("_dev_cache", {})
    if did in cache:
        dd = cache[did]
        name = dd.get("deviceName") or dd.get("name") or did[:20]
        sims = dd.get("sims", [])
        fb_id = fsmd.get("wiz_fb", "")
        if did not in [x["id"] for x in u.get("devices", [])]:
            u["devices"].append({"id": did, "name": name, "fb_id": fb_id, "sims": sims})
        save(d)
        if fsmd.get("wizard"):
            merged = dict(fsmd)
            merged.update(
                {
                    "wiz_dev": did,
                    "wiz_sims_avail": sims,
                    "wiz_sims_sel": [],
                }
            )
            await state.update_data(**merged)
            if sims:
                await msg.answer(
                    wiz_card(3, 5, "Select SIM(s)", "Tap to toggle ✅"),
                    reply_markup=sim_kb(sims, [], did),
                    parse_mode="HTML",
                )
            else:
                merged["wiz_sims"] = [0]
                await state.update_data(**merged)
                await msg.answer(
                    wiz_card(4, 5, "Channel Type", "Public ya Private?"),
                    reply_markup=ch_type_kb(),
                    parse_mode="HTML",
                )
        else:
            await state.clear()
            await msg.answer(
                f"✅ Device <b>{name}</b> added!",
                reply_markup=list_kb(
                    u["devices"], "id", "name", "dev:del:", "dev:add", "my:menu"
                ),
                parse_mode="HTML",
            )
    else:
        await msg.answer(f"❌ <code>{did}</code> not found. Try again:", parse_mode="HTML")


@R.message(W.ch_pub_input)
async def f_ch_pub_input(msg: Message, state: FSMContext):
    d = load()
    uid = msg.from_user.id
    text = msg.text.strip()
    u = usr(uid, d)
    cid = int(text) if text.lstrip("-").isdigit() else text
    if str(cid) not in [str(c["id"]) for c in u.get("channels", [])]:
        u["channels"].append({"id": cid, "name": text, "type": "public"})
    save(d)
    fsmd = await state.get_data()
    if fsmd.get("wizard"):
        merged = dict(fsmd)
        merged.update(
            {
                "wiz_ch": cid,
                "wiz_ch_type": "public",
                "wiz_ch_name": text,
                "wiz_ch_token": "",
            }
        )
        await state.update_data(**merged)
        await msg.answer(
            wiz_card(5, 5, "Repeat Count", "How many times per SMS?"),
            reply_markup=repeat_kb(),
            parse_mode="HTML",
        )
    else:
        await state.clear()
        await msg.answer(
            f"✅ Public channel <code>{text}</code> added!",
            reply_markup=channels_kb(u["channels"]),
            parse_mode="HTML",
        )


@R.message(W.ch_priv_token)
async def f_ch_priv_token(msg: Message, state: FSMContext):
    token = msg.text.strip()
    if not re.match(r"^\d+:[A-Za-z0-9_-]{30,}$", token):
        await msg.answer(
            "❌ Yeh valid bot token nahi lag raha.\n\n"
            "Format: <code>123456789:ABCdefGHIjklMNOpqrSTUvwxYZ</code>\n"
            "BotFather se <code>/token</code> se nikaalo.",
            parse_mode="HTML",
        )
        return
    fsmd = await state.get_data()
    merged = dict(fsmd)
    merged["wiz_ch_token"] = token
    await state.update_data(**merged)
    await state.set_state(W.ch_priv_chatid)
    await msg.answer(
        "✅ Token save.\n\n"
        "Ab us private channel ka <b>Chat ID</b> bhejo:\n"
        "Format: <code>-1001234567890</code>\n\n"
        "Nikalne ka tarika: channel ka koi message\n"
        "<code>@userinfobot</code> ko forward karo.",
        parse_mode="HTML",
        reply_markup=kb([("❌ Cancel", "home")]),
    )


@R.message(W.ch_priv_chatid)
async def f_ch_priv_chatid(msg: Message, state: FSMContext):
    raw = msg.text.strip()
    if not (raw.lstrip("-").isdigit() or raw.startswith("@")):
        await msg.answer(
            "❌ Chat ID numeric honi chahiye (<code>-100…</code>) ya @username.",
            parse_mode="HTML",
        )
        return
    chat_id = int(raw) if raw.lstrip("-").isdigit() else raw
    fsmd = await state.get_data()
    token = fsmd.get("wiz_ch_token", "")
    uid = msg.from_user.id

    if not token:
        await state.clear()
        await msg.answer(
            "❌ Token missing. Wizard dobara chalao.",
            reply_markup=kb([("🏠 Home", "home")]),
        )
        return

    wait = await msg.answer("🔎 Verifying private channel…")
    ok, title, err = await verify_private_channel(token, chat_id)
    try:
        await wait.delete()
    except Exception:
        pass

    if not ok:
        await msg.answer(
            f"❌ <b>Verification failed</b>\n\n<code>{err}</code>\n\n"
            f"Check karo:\n"
            f"• Bot us channel mein <b>admin</b> hai?\n"
            f"• Post Messages permission ON hai?\n"
            f"• Chat ID sahi hai?\n\n"
            f"Wapas try karo:",
            parse_mode="HTML",
            reply_markup=kb([("🔁 Retry", "ch:retry_private"), ("❌ Cancel", "home")]),
        )
        return

    d = load()
    u = usr(uid, d)
    if str(chat_id) not in [str(c["id"]) for c in u.get("channels", [])]:
        u["channels"].append(
            {"id": chat_id, "name": title or str(chat_id), "type": "private", "token": token}
        )
    save(d)

    if fsmd.get("wizard"):
        merged = dict(fsmd)
        merged.update(
            {
                "wiz_ch": chat_id,
                "wiz_ch_type": "private",
                "wiz_ch_token": token,
                "wiz_ch_name": title or str(chat_id),
            }
        )
        await state.update_data(**merged)
        await msg.answer(
            f"✅ Private channel verified: <b>{title}</b>\n\n"
            + wiz_card(5, 5, "Repeat Count", "How many times per SMS?"),
            reply_markup=repeat_kb(),
            parse_mode="HTML",
        )
    else:
        await state.clear()
        await msg.answer(
            f"✅ Private channel <b>{title}</b> added!\n"
            f"Connection confirmation channel mein bhej di.",
            reply_markup=channels_kb(u["channels"]),
            parse_mode="HTML",
        )
        await send_channel_confirmation(
            token,
            chat_id,
            "✅ <b>SMS Bot successfully connected to this channel.</b>\n\n"
            "Koi bhi SMS-format message post karein — bot auto-forward karega.",
        )


@R.message(W.ch_input)
async def f_ch_input(msg: Message, state: FSMContext):
    await state.set_state(W.ch_pub_input)
    await f_ch_pub_input(msg, state)


@R.message(W.repeat_cust)
async def f_repeat_cust(msg: Message, state: FSMContext):
    d = load()
    uid = msg.from_user.id
    try:
        n = int(msg.text.strip())
        if not 1 <= n <= 20:
            raise ValueError
    except Exception:
        await msg.answer("❌ Enter 1–20.")
        return
    fsmd = await state.get_data()
    if fsmd.get("wizard"):
        await state.clear()
        await _wiz_finish(msg.bot, uid, {**fsmd, "wiz_repeat": n}, d)
    else:
        await state.clear()
        await msg.answer("✅ Set!", reply_markup=main_menu(uid, d))


@R.message(W.test_to)
async def f_test_to(msg: Message, state: FSMContext):
    await state.update_data(test_to=msg.text.strip())
    await state.set_state(W.test_msg)
    await msg.answer("💬 Enter message text:")


@R.message(W.test_msg)
async def f_test_msg(msg: Message, state: FSMContext):
    d = load()
    uid = msg.from_user.id
    fsmd = await state.get_data()
    to = fsmd.get("test_to", "")
    u = usr(uid, d)
    ac = u.get("active", {})
    await state.clear()
    if not ac.get("fb_url"):
        await msg.answer("❌ No active combo. Run wizard first.")
        return
    wait = await msg.answer("📤 Sending…")
    ok = await send_via_fb(
        ac["fb_url"], ac["device_id"], ac.get("sims", [0])[0], to, msg.text.strip()
    )
    try:
        await wait.delete()
    except Exception:
        pass
    await msg.answer(
        f"{'✅ Sent!' if ok else '❌ Failed!'}\n📞 <code>{to}</code>",
        reply_markup=kb([("🏠 Home", "home")]),
        parse_mode="HTML",
    )


@R.message(W.fwd_add)
async def f_fwd_add(msg: Message, state: FSMContext):
    d = load()
    uid = msg.from_user.id
    u = usr(uid, d)
    if msg.text.strip() not in u["fwd"]:
        u["fwd"].append(msg.text.strip())
    save(d)
    await state.clear()
    await msg.answer(
        f"✅ Added: <code>{msg.text.strip()}</code>",
        reply_markup=_fwd_kb(uid, d),
        parse_mode="HTML",
    )


@R.message(W.adm_add)
async def f_adm_add(msg: Message, state: FSMContext):
    d = load()
    if not (is_owner(msg.from_user.id) or is_super_admin(msg.from_user.id, d)):
        await state.clear()
        return
    try:
        nid = int(msg.text.strip())
        if nid not in d["admins"]:
            d["admins"].append(nid)
        save(d)
        await state.clear()
        await msg.answer(
            f"✅ Admin added: <code>{nid}</code>",
            reply_markup=adm_menu_kb(msg.from_user.id, d),
            parse_mode="HTML",
        )
        await safe_send(msg.bot, nid, "🎉 You're now an <b>Admin</b>! Send /start", parse_mode="HTML")
    except Exception:
        await msg.answer("❌ Invalid user ID.")


@R.message(W.ban_id)
async def f_ban_id(msg: Message, state: FSMContext):
    d = load()
    if not is_admin(msg.from_user.id, d):
        await state.clear()
        return
    try:
        bid = int(msg.text.strip())
        if is_admin(bid, d):
            await msg.answer("❌ Admin ko ban nahi kar sakte!")
            return
        if bid not in d.setdefault("banned", []):
            d["banned"].append(bid)
        save(d)
        await state.clear()
        await msg.answer(
            f"🚫 <b>Ban ho gaya:</b> <code>{bid}</code>",
            reply_markup=adm_menu_kb(msg.from_user.id, d),
            parse_mode="HTML",
        )
        await safe_send(msg.bot, bid, "🚫 Aapko ban kar diya gaya hai. Admin se sampark karein.")
    except Exception:
        await msg.answer("❌ Invalid user ID. Sirf numeric ID bhejo.")


@R.message(W.sadm_add)
async def f_sadm_add(msg: Message, state: FSMContext):
    if not is_owner(msg.from_user.id):
        await state.clear()
        return
    d = load()
    try:
        nid = int(msg.text.strip())
        if nid not in d.setdefault("super_admins", []):
            d["super_admins"].append(nid)
        save(d)
        await state.clear()
        await msg.answer(
            f"✅ Super Admin added: <code>{nid}</code>",
            reply_markup=sadm_menu_kb(d),
            parse_mode="HTML",
        )
        await safe_send(msg.bot, nid, "🌟 You're now a <b>Super Admin</b>! Send /start", parse_mode="HTML")
    except Exception:
        await msg.answer("❌ Invalid user ID.")


@R.message(W.usr_add_id)
async def f_usr_add_id(msg: Message, state: FSMContext):
    try:
        uid2 = int(msg.text.strip())
        await state.update_data(new_uid=uid2)
        await state.set_state(W.usr_add_exp)
        await msg.answer(
            f"✅ User ID: <code>{uid2}</code>\n\n⏱ <b>Select access duration:</b>",
            reply_markup=timed_kb(),
            parse_mode="HTML",
        )
    except Exception:
        await msg.answer("❌ Send a valid Telegram user ID.")


@R.message(W.usr_add_exp)
async def f_usr_add_exp(msg: Message, state: FSMContext):
    d = load()
    uid = msg.from_user.id
    text = msg.text.strip()
    fsmd = await state.get_data()
    uid2 = fsmd.get("new_uid")
    await state.clear()
    try:
        exp = None
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
            try:
                dt = datetime.strptime(text, fmt)
                exp = dt.timestamp()
                break
            except ValueError:
                continue
        if exp is None:
            raise ValueError
        _add_timed(uid2, exp, uid, d)
        save(d)
        await msg.answer(
            f"✅ User <code>{uid2}</code> added until <code>{text}</code>",
            reply_markup=adm_menu_kb(uid, d),
            parse_mode="HTML",
        )
        await safe_send(
            msg.bot, uid2, f"✅ Access until <code>{text}</code>.\nSend /start", parse_mode="HTML"
        )
    except Exception:
        await msg.answer("❌ Invalid date. Use DD/MM/YYYY")


@R.message(W.fj_add)
async def f_fj_add(msg: Message, state: FSMContext):
    d = load()
    if not (is_owner(msg.from_user.id) or is_super_admin(msg.from_user.id, d)):
        await state.clear()
        return

    uid = msg.from_user.id
    text = msg.text.strip()
    fsmd = await state.get_data()

    if fsmd.get("fj_step") == "awaiting_title":
        link = fsmd.get("fj_link", "")
        chat_id = fsmd.get("fj_chat_id", "")
        title = text
        fj = d.setdefault("force_join", [])
        if not any(str(c["id"]) == str(chat_id) for c in fj):
            fj.append({"id": chat_id, "title": title, "link": link})
        save(d)
        await state.clear()
        await msg.answer(
            f"✅ <b>Force Join Added!</b>\n\n"
            f"📢 <b>{title}</b>\n"
            f"🆔 <code>{str(chat_id)[:40]}</code>\n"
            f"🔗 <code>{str(link)[:40] or '—'}</code>\n\n"
            f"⚠️ <i>Bot ko us channel/group mein admin banana zaroori hai!</i>",
            reply_markup=fj_menu_kb(uid, load()),
            parse_mode="HTML",
        )
        return

    if fsmd.get("fj_step") == "awaiting_chat_id":
        raw = text
        if raw.lstrip("-").isdigit():
            chat_id = int(raw)
        elif raw.startswith("@"):
            chat_id = raw
        else:
            await msg.answer(
                "❌ Sahi Chat ID bhejo:\n"
                "• Numeric: <code>-1001234567890</code>\n"
                "• Ya: <code>@username</code>",
                parse_mode="HTML",
            )
            return
        await state.update_data(fj_step="awaiting_title", fj_chat_id=chat_id)
        await msg.answer(
            f"✅ Chat ID save: <code>{chat_id}</code>\n\n"
            f"Ab <b>display name</b> bhejo:",
            parse_mode="HTML",
            reply_markup=kb([("❌ Cancel", "fj:menu")]),
        )
        return

    tm = re.search(r"t\.me/([+\w]+)", text)
    if tm:
        link = f"https://t.me/{tm.group(1)}"
    elif text.startswith("@"):
        link = f"https://t.me/{text.lstrip('@')}"
    elif text.startswith("http"):
        link = text
    elif text.lstrip("-").isdigit():
        chat_id = int(text)
        await state.update_data(fj_step="awaiting_title", fj_link="", fj_chat_id=chat_id)
        await msg.answer(
            f"✅ Chat ID mila: <code>{chat_id}</code>\n\n"
            f"Ab <b>display name</b> bhejo:",
            parse_mode="HTML",
            reply_markup=kb([("❌ Cancel", "fj:menu")]),
        )
        return
    else:
        link = f"https://t.me/{text.lstrip('@')}"

    await state.update_data(fj_step="awaiting_chat_id", fj_link=link)
    await msg.answer(
        f"✅ Link save: <code>{link}</code>\n\n"
        f"Ab <b>Chat ID</b> bhejo:",
        parse_mode="HTML",
        reply_markup=kb([("❌ Cancel", "fj:menu")]),
    )


# ══════════════════════════════════════════════
#  CALLBACKS
# ══════════════════════════════════════════════
@R.callback_query()
async def cb(cq: CallbackQuery, state: FSMContext):
    d = load()
    uid = cq.from_user.id
    c = cq.data
    if not can_use(uid, d):
        await cq.answer("🚫 You are banned.", show_alert=True)
        return
    u = usr(uid, d)

    if c in ("home", "fj:check"):
        await state.clear()
        ok, not_joined = await check_force_join(cq.bot, uid, d)
        if not ok:
            await sedit(
                cq,
                "📢 <b>Join Required</b>\n\nJoin all channels to continue:",
                _fj_keyboard(not_joined),
            )
            if c == "fj:check":
                await cq.answer("❌ Please join all channels first!", show_alert=True)
            return
        await sedit(cq, home_text(uid, d), main_menu(uid, d))
        if c == "fj:check":
            await cq.answer("✅ Verified! Welcome!", show_alert=True)

    elif c == "paste:toggle":
        d2 = load()
        u2 = usr(uid, d2)
        u2["paste_mode"] = not bool(u2.get("paste_mode", True))
        save(d2)
        state_txt = "ON ✅" if u2["paste_mode"] else "OFF 🔴"
        await cq.answer(f"Paste mode: {state_txt}")
        await sedit(cq, home_text(uid, d2), main_menu(uid, d2))

    elif c == "help:show":
        await sedit(cq, HELP_TEXT, kb([("🔙 Back", "home")]))

    elif c == "wiz:start":
        await state.clear()
        fbs = u.get("firebases", [])
        ac = u.get("active", {})
        if ac.get("fb_url"):
            await sedit(
                cq,
                "⚠️ <b>Combo already setup hai!</b>\n\n"
                "Naya setup ke liye pehle <b>Reset Me</b>.",
                kb([("🗑 Reset & Setup New", "wiz:reset_and_start"), ("🔙 Back", "home")]),
                parse_mode="HTML",
            )
        else:
            await state.update_data(wizard=True)
            await state.set_state(W.fb_url)
            await sedit(
                cq,
                wiz_card(1, 5, "Firebase URL", "https://your-project.firebaseio.com"),
                kb([("❌ Cancel", "home")]),
            )

    elif c == "wiz:reset_and_start":
        d2 = load()
        u2 = usr(uid, d2)
        u2["firebases"] = []
        u2["devices"] = []
        u2["active"] = {}
        u2["monitoring"] = False
        save(d2)
        await state.clear()
        await state.update_data(wizard=True)
        await state.set_state(W.fb_url)
        await sedit(
            cq,
            wiz_card(1, 5, "Firebase URL", "https://your-project.firebaseio.com"),
            kb([("❌ Cancel", "home")]),
        )

    elif c == "wiz:retry_dev":
        fsmd = await state.get_data()
        if fsmd.get("wiz_fb_url"):
            await _wiz_fetch_devices(cq.bot, uid, fsmd["wiz_fb_url"], fsmd.get("wiz_fb", ""), cq)

    elif c.startswith("wpick:fb:"):
        fid = c.split("wpick:fb:", 1)[1]
        fb = next((f for f in u.get("firebases", []) if f["id"] == fid), None)
        if not fb:
            await cq.answer("Not found!", show_alert=True)
            return
        merged = {"wizard": True, "wiz_fb": fid, "wiz_fb_url": fb["url"]}
        await state.update_data(**merged)
        await _wiz_fetch_devices(cq.bot, uid, fb["url"], fid, cq)

    elif c.startswith("faddpg:"):
        page = int(c.split(":")[1])
        cache = u.get("_dev_cache", {})
        online = {k: v for k, v in cache.items() if dev_online(v)}
        await sedit(
            cq, wiz_card(2, 5, "Select Device", f"Page {page+1}"), online_devs_kb(online, page)
        )

    elif c.startswith("fadd:"):
        did = c.split("fadd:", 1)[1]
        cache = u.get("_dev_cache", {})
        dd = cache.get(did, {})
        name = dd.get("deviceName") or dd.get("name") or did[:20]
        sims = dd.get("sims", [])
        fsmd = await state.get_data()
        if did not in [x["id"] for x in u.get("devices", [])]:
            u["devices"].append(
                {"id": did, "name": name, "fb_id": fsmd.get("wiz_fb", ""), "sims": sims}
            )
            save(d)
        if sims:
            merged = dict(fsmd)
            merged.update(
                {
                    "wiz_dev": did,
                    "wiz_sims_avail": sims,
                    "wiz_sims_sel": [],
                }
            )
            await state.update_data(**merged)
            await sedit(
                cq, wiz_card(3, 5, "Select SIM(s)", "Tap to toggle ✅"), sim_kb(sims, [], did)
            )
        else:
            merged = dict(fsmd)
            merged.update(
                {
                    "wiz_dev": did,
                    "wiz_sims": [0],
                }
            )
            await state.update_data(**merged)
            await sedit(cq, wiz_card(4, 5, "Channel Type", "Public ya Private?"), ch_type_kb())

    elif c == "dev:manual":
        fsmd = await state.get_data()
        await state.update_data(**fsmd)
        await state.set_state(W.dev_manual)
        await sedit(cq, "🔍 Enter Device ID manually:", kb([("❌ Cancel", "home")]))

    elif c.startswith("simtog:"):
        parts = c.split(":")
        did = parts[1]
        idx = int(parts[2])
        fsmd = await state.get_data()
        sel = list(fsmd.get("wiz_sims_sel", []))
        if idx in sel:
            sel.remove(idx)
        else:
            sel.append(idx)
        merged = dict(fsmd)
        merged["wiz_sims_sel"] = sel
        await state.update_data(**merged)
        sims = fsmd.get("wiz_sims_avail", [])
        await sedit(
            cq, wiz_card(3, 5, "Select SIM(s)", f"{len(sel)} selected"), sim_kb(sims, sel, did)
        )

    elif c.startswith("simok:"):
        fsmd = await state.get_data()
        sel = fsmd.get("wiz_sims_sel", [])
        if not sel:
            await cq.answer("Select at least one SIM!", show_alert=True)
            return
        merged = dict(fsmd)
        merged["wiz_sims"] = sel
        await state.update_data(**merged)
        await sedit(cq, wiz_card(4, 5, "Channel Type", "Public ya Private?"), ch_type_kb())

    elif c == "ch:type:public":
        await state.set_state(W.ch_pub_input)
        await sedit(
            cq,
            wiz_card(4, 5, "Public Channel", "@username or chat ID"),
            kb([("❌ Cancel", "home")]),
        )

    elif c == "ch:type:private":
        await state.set_state(W.ch_priv_token)
        await sedit(
            cq,
            wiz_card(4, 5, "Private Channel — Step 1/2", "Bot token paste karo"),
            kb([("❌ Cancel", "home")]),
        )

    elif c == "ch:picktype":
        await sedit(cq, "📺 <b>Add Channel</b>\n\nKaunsa type?", ch_type_kb())

    elif c == "ch:retry_private":
        await state.set_state(W.ch_priv_chatid)
        await sedit(
            cq,
            wiz_card(4, 5, "Private Channel — Step 2/2", "Chat ID bhejo"),
            kb([("❌ Cancel", "home")]),
        )

    elif c.startswith("wpick:ch:"):
        cid = c.split("wpick:ch:", 1)[1]
        ch = next((x for x in u.get("channels", []) if str(x["id"]) == str(cid)), None)
        if not ch:
            await cq.answer("Not found!", show_alert=True)
            return
        fsmd = await state.get_data()
        merged = dict(fsmd)
        merged.update(
            {
                "wiz_ch": ch["id"],
                "wiz_ch_type": ch.get("type", "public"),
                "wiz_ch_token": ch.get("token", ""),
                "wiz_ch_name": ch.get("name", ""),
            }
        )
        await state.update_data(**merged)
        await sedit(cq, wiz_card(5, 5, "Repeat Count", "Times to send per SMS"), repeat_kb())

    elif c.startswith("wpick:dev:"):
        did = c.split("wpick:dev:", 1)[1]
        dv = next((x for x in u.get("devices", []) if x["id"] == did), None)
        if not dv:
            await cq.answer("Not found!", show_alert=True)
            return
        sims = dv.get("sims", [])
        fsmd = await state.get_data()
        if sims:
            merged = dict(fsmd)
            merged.update(
                {
                    "wiz_dev": did,
                    "wiz_sims_avail": sims,
                    "wiz_sims_sel": [],
                }
            )
            await state.update_data(**merged)
            await sedit(cq, wiz_card(3, 5, "Select SIM(s)", "Tap to toggle"), sim_kb(sims, [], did))
        else:
            merged = dict(fsmd)
            merged.update({"wiz_dev": did, "wiz_sims": [0]})
            await state.update_data(**merged)
            await sedit(cq, wiz_card(4, 5, "Channel Type", "Public ya Private?"), ch_type_kb())

    elif c.startswith("wpick:devpg:"):
        page = int(c.split(":")[-1])
        await sedit(
            cq,
            wiz_card(2, 5, "Select Device", f"Page {page+1}"),
            dev_pick_kb(u.get("devices", []), page),
        )

    elif c.startswith("rpt:"):
        val = c.split(":")[1]
        fsmd = await state.get_data()
        if val == "c":
            await state.update_data(**fsmd)
            await state.set_state(W.repeat_cust)
            await sedit(cq, "✏️ Enter repeat count (1–20):", kb([("❌ Cancel", "home")]))
        else:
            rpt = int(val)
            await state.clear()
            await sedit(cq, "⏳ Starting monitor…")
            await _wiz_finish(cq.bot, uid, {**fsmd, "wiz_repeat": rpt}, load())

    elif c == "mon:go":
        fresh = load()
        uf = usr(uid, fresh)
        if uf.get("monitoring"):
            _stop_mon(uid)
            uf["monitoring"] = False
            save(fresh)
            await sedit(cq, "⏸ <b>Monitor Stopped.</b>", main_menu(uid, fresh))
        else:
            ac = uf.get("active", {})
            if not ac.get("fb_url") or not ac.get("device_id"):
                await cq.answer("❌ Setup incomplete. Run Setup Wizard first!", show_alert=True)
                return
            uf["monitoring"] = True
            save(fresh)
            _start_mon(cq.bot, uid)
            await sedit(cq, "🟢 <b>Monitor Started!</b>", main_menu(uid, fresh))

    elif c == "dash:show":
        d2 = load()
        u2 = usr(uid, d2)
        await sedit(
            cq,
            f"📊 <b>Dashboard</b>\n\n{combo_card(u2)}\n\n{stats_card(u2)}\n\n{setup_card(u2)}",
            kb([("🔄 Refresh", "dash:show"), ("🏠 Home", "home")]),
        )

    elif c == "my:menu":
        await sedit(
            cq,
            "⚙️ <b>My Settings</b>",
            kb(
                [
                    (f"🔥 Firebase ({len(u.get('firebases', []))})", "fb:list"),
                    (f"📱 Devices ({len(u.get('devices', []))})", "dev:list"),
                ],
                [
                    (f"📺 Channels ({len(u.get('channels', []))})", "ch:list"),
                    ("🧪 Test SMS", "test:go"),
                ],
                [("🔙 Back", "home")],
            ),
        )

    elif c == "fb:list":
        await sedit(
            cq,
            "🔥 <b>Firebase URLs</b>",
            list_kb(u.get("firebases", []), "id", "url", "fb:del:", "fb:add", "my:menu"),
        )

    elif c == "fb:add":
        await state.set_state(W.fb_url)
        await sedit(cq, "🔥 Send Firebase URL:", kb([("❌ Cancel", "fb:list")]))

    elif c.startswith("fb:del:"):
        fid = c.split("fb:del:", 1)[1]
        u["firebases"] = [f for f in u.get("firebases", []) if f["id"] != fid]
        save(d)
        await cq.answer("🗑 Removed.")
        await sedit(
            cq,
            "🔥 <b>Firebase URLs</b>",
            list_kb(u.get("firebases", []), "id", "url", "fb:del:", "fb:add", "my:menu"),
        )

    elif c == "dev:list":
        await sedit(
            cq,
            "📱 <b>Devices</b>",
            list_kb(u.get("devices", []), "id", "name", "dev:del:", "dev:add", "my:menu"),
        )

    elif c == "dev:add":
        fbs = u.get("firebases", [])
        if not fbs:
            await cq.answer("❌ Add Firebase first!", show_alert=True)
            return
        fb = fbs[0]
        merged = {"wizard": False, "wiz_fb": fb["id"], "wiz_fb_url": fb["url"]}
        await state.update_data(**merged)
        await _wiz_fetch_devices(cq.bot, uid, fb["url"], fb["id"], cq)

    elif c.startswith("dev:del:"):
        did = c.split("dev:del:", 1)[1]
        u["devices"] = [x for x in u.get("devices", []) if x["id"] != did]
        save(d)
        await cq.answer("🗑 Removed.")
        await sedit(
            cq,
            "📱 <b>Devices</b>",
            list_kb(u.get("devices", []), "id", "name", "dev:del:", "dev:add", "my:menu"),
        )

    elif c == "ch:list":
        await sedit(
            cq, "📺 <b>Channels</b>\n\n🌐 public · 🔒 private", channels_kb(u.get("channels", []))
        )

    elif c == "ch:add:public":
        await state.set_state(W.ch_pub_input)
        await sedit(
            cq, "📺 Send public channel <code>@username</code> or chat ID:", kb([("❌ Cancel", "ch:list")])
        )

    elif c == "ch:add:private":
        await state.set_state(W.ch_priv_token)
        await sedit(
            cq,
            "🔒 <b>Private Channel — Step 1/2</b>\n\n"
            "Us channel ke bot ka <b>token</b> bhejo.\n"
            "Format: <code>123456789:ABCdef…</code>\n\n"
            "BotFather se <code>/newbot</code> → token copy.",
            kb([("❌ Cancel", "ch:list")]),
        )

    elif c == "ch:add":
        await sedit(cq, "📺 <b>Add Channel</b>\n\nKaunsa type?", ch_type_kb())

    elif c.startswith("ch:del:"):
        cid = c.split("ch:del:", 1)[1]
        u["channels"] = [x for x in u.get("channels", []) if str(x["id"]) != cid]
        save(d)
        await cq.answer("🗑 Removed.")
        await sedit(cq, "📺 <b>Channels</b>", channels_kb(u.get("channels", [])))

    elif c == "test:go":
        if not u.get("active", {}).get("fb_url"):
            await cq.answer("❌ Run wizard first!", show_alert=True)
            return
        await state.set_state(W.test_to)
        await sedit(
            cq, "🧪 <b>Test SMS</b>\n\nEnter recipient number:", kb([("❌ Cancel", "my:menu")])
        )

    elif c == "fwd:menu":
        await sedit(cq, "📤 <b>Forward Targets</b>", _fwd_kb(uid, d))

    elif c == "fwd:add":
        await state.set_state(W.fwd_add)
        await sedit(
            cq, "📤 Send <code>@username</code> or chat ID:", kb([("❌ Cancel", "fwd:menu")])
        )

    elif c.startswith("fwd:del:"):
        tgt = c.split("fwd:del:", 1)[1]
        u["fwd"] = [t for t in u.get("fwd", []) if str(t) != tgt]
        save(d)
        await cq.answer("🗑 Removed.")
        await sedit(cq, "📤 <b>Forward Targets</b>", _fwd_kb(uid, d))

    elif c == "reset:self":
        await sedit(
            cq, "⚠️ <b>Reset your data?</b>", kb([("✅ Yes", "reset:self:yes"), ("❌ Cancel", "home")])
        )

    elif c == "reset:self:yes":
        _stop_mon(uid)
        d2 = load()
        d2["users"][str(uid)] = _new_user()
        save(d2)
        await sedit(cq, "✅ <b>Data reset.</b>", main_menu(uid, load()))

    elif c == "adm:menu":
        if not is_admin(uid, d):
            await cq.answer("🚫", show_alert=True)
            return
        await sedit(cq, "🛡 <b>Admin Tools</b>", adm_menu_kb(uid, d))

    elif c == "adm:users":
        if not is_admin(uid, d):
            await cq.answer("🚫", show_alert=True)
            return
        lines = ["👥 <b>All Users:</b>\n"]
        for k, v in d.get("users", {}).items():
            mon = "🟢" if v.get("monitoring") else "🔴"
            s = v.get("stats", {})
            lines.append(f"  {mon} <code>{k}</code> ✅{s.get('sent', 0)} ❌{s.get('failed', 0)}")
        for k, v in d.get("timed_users", {}).items():
            rem = v.get("expires", 0)
            exp = datetime.fromtimestamp(rem).strftime("%d/%m %H:%M") if rem else "∞"
            lines.append(f"  ⏱ <code>{k}</code> exp:{exp}")
        await sedit(cq, "\n".join(lines) or "No users.", kb([("🔙 Back", "adm:menu")]))

    elif c == "adm:adduser":
        if not is_admin(uid, d):
            await cq.answer("🚫", show_alert=True)
            return
        await state.set_state(W.usr_add_id)
        await sedit(cq, "👤 <b>Add User</b>\n\nSend Telegram user ID:", kb([("❌ Cancel", "adm:menu")]))

    elif c.startswith("tacc:"):
        val = c.split(":")[1]
        fsmd = await state.get_data()
        uid2 = fsmd.get("new_uid")
        if not uid2:
            await cq.answer("Session expired.", show_alert=True)
            return
        if val == "custom":
            await state.set_state(W.usr_add_exp)
            await sedit(cq, "📅 Send expiry date (DD/MM/YYYY):", kb([("❌ Cancel", "adm:menu")]))
            return
        secs = int(val)
        exp = None if secs == 0 else time.time() + secs
        d2 = load()
        _add_timed(uid2, exp, uid, d2)
        save(d2)
        await state.clear()
        label = "Permanent ♾" if secs == 0 else f"{secs//3600}h"
        await sedit(
            cq, f"✅ User <code>{uid2}</code> — <b>{label}</b>", adm_menu_kb(uid, d2)
        )
        m2 = "♾ Permanent" if secs == 0 else f"⏱ {secs//3600}h"
        await safe_send(cq.bot, uid2, f"Access: <b>{m2}</b>\nSend /start", parse_mode="HTML")

    elif c == "adm:stats":
        if not is_admin(uid, d):
            await cq.answer("🚫", show_alert=True)
            return
        users = d.get("users", {})
        ts = 0
        tf = 0
        for v in users.values():
            s = v.get("stats", {})
            ts += s.get("sent", 0)
            tf += s.get("failed", 0)
        bar = pbar(ts, ts + tf, "round", 8) if ts + tf else "○" * 8
        await sedit(
            cq,
            f"📊 <b>Global Stats</b>\n\n"
            f"  {bar}  {pct(ts, ts+tf)}\n\n"
            f"  👥 Users      : <code>{len(users)}</code>\n"
            f"  🟢 Monitoring : <code>{sum(1 for v in users.values() if v.get('monitoring'))}</code>\n"
            f"  ✅ Total Sent : <code>{ts}</code>\n"
            f"  ❌ Total Fail : <code>{tf}</code>",
            kb([("🔙 Back", "adm:menu")]),
        )

    elif c == "adm:free":
        if not (is_owner(uid) or is_super_admin(uid, d)):
            await cq.answer("🚫 Owner/Super Admin only!", show_alert=True)
            return
        d["free"] = not d.get("free", False)
        save(d)
        await cq.answer(f"Free Mode: {'ON ✅' if d['free'] else 'OFF 🔴'}")
        await sedit(cq, "🛡 <b>Admin Tools</b>", adm_menu_kb(uid, d))

    elif c == "adm:addadmin":
        if not (is_owner(uid) or is_super_admin(uid, d)):
            await cq.answer("🚫", show_alert=True)
            return
        await state.set_state(W.adm_add)
        await sedit(cq, "➕ <b>Add Admin</b>\n\nSend Telegram user ID:", kb([("❌ Cancel", "adm:menu")]))

    elif c == "adm:zip":
        if not is_owner(uid):
            await cq.answer("🚫 Owner only!", show_alert=True)
            return
        await cq.answer("📦 Preparing…")
        zdata = make_zip()
        fname = f"smsbot_{datetime.now().strftime('%Y%m%d_%H%M')}.zip"
        await cq.bot.send_document(
            uid,
            BufferedInputFile(zdata, filename=fname),
            caption=f"📦 <b>Export</b> <code>{fname}</code>\n<i>by {_CREDITS}</i>",
            parse_mode="HTML",
        )

    elif c == "adm:resetall":
        if not is_owner(uid):
            await cq.answer("🚫 Owner only!", show_alert=True)
            return
        await sedit(
            cq,
            "💥 <b>Reset ALL users?</b>",
            kb([("✅ Yes", "adm:resetall:yes"), ("❌ Cancel", "adm:menu")]),
        )

    elif c == "adm:resetall:yes":
        if not is_owner(uid):
            await cq.answer("🚫", show_alert=True)
            return
        for t in _tasks.values():
            t.cancel()
        _tasks.clear()
        _seen.clear()
        d2 = load()
        d2["users"] = {}
        d2["timed_users"] = {}
        save(d2)
        await sedit(cq, "💥 <b>All data reset.</b>", adm_menu_kb(uid, load()))

    elif c == "ban:do":
        if not is_admin(uid, d):
            await cq.answer("🚫", show_alert=True)
            return
        await state.set_state(W.ban_id)
        await sedit(cq, "🚫 <b>Ban User</b>\n\nTelegram User ID bhejo:", kb([("❌ Cancel", "adm:menu")]))

    elif c == "unban:do":
        if not is_admin(uid, d):
            await cq.answer("🚫", show_alert=True)
            return
        banned = d.get("banned", [])
        if not banned:
            await cq.answer("✅ Koi bhi banned nahi hai!", show_alert=True)
            return
        rows = [[(f"🔓 {bid}", f"unban:uid:{bid}")] for bid in banned]
        rows.append([("❌ Cancel", "adm:menu")])
        await sedit(
            cq,
            "✅ <b>Banned Users — Unban karo:</b>",
            InlineKeyboardMarkup(inline_keyboard=rows),
        )

    elif c.startswith("unban:uid:"):
        if not is_admin(uid, d):
            await cq.answer("🚫", show_alert=True)
            return
        bid = int(c.split("unban:uid:", 1)[1])
        d2 = load()
        if bid in d2.get("banned", []):
            d2["banned"].remove(bid)
        save(d2)
        await cq.answer(f"✅ {bid} unban ho gaya!", show_alert=True)
        await sedit(
            cq, f"✅ <b>Unban ho gaya:</b> <code>{bid}</code>", adm_menu_kb(uid, d2)
        )
        await safe_send(cq.bot, bid, "✅ Aapka ban hata diya gaya. /start karein.", parse_mode="HTML")

    elif c == "sadm:menu":
        if not is_owner(uid):
            await cq.answer("🚫 Owner only!", show_alert=True)
            return
        await sedit(cq, "🌟 <b>Super Admins</b>", sadm_menu_kb(d))

    elif c == "sadm:add":
        if not is_owner(uid):
            await cq.answer("🚫 Owner only!", show_alert=True)
            return
        await state.set_state(W.sadm_add)
        await sedit(
            cq, "🌟 <b>Add Super Admin</b>\n\nSend Telegram user ID:", kb([("❌ Cancel", "sadm:menu")])
        )

    elif c.startswith("sadm:del:"):
        if not is_owner(uid):
            await cq.answer("🚫 Owner only!", show_alert=True)
            return
        sid = int(c.split("sadm:del:", 1)[1])
        if sid in SUPER_ADMINS:
            await cq.answer("🚫 Cannot remove hardcoded Super Admin.", show_alert=True)
            return
        d2 = load()
        if sid in d2.get("super_admins", []):
            d2["super_admins"].remove(sid)
        save(d2)
        await cq.answer("🗑 Removed.")
        await sedit(cq, "🌟 <b>Super Admins</b>", sadm_menu_kb(d2))

    elif c == "fj:menu":
        if not is_admin(uid, d):
            await cq.answer("🚫", show_alert=True)
            return
        await sedit(cq, "📢 <b>Force Join Channels</b>", fj_menu_kb(uid, d))

    elif c == "fj:add":
        if not (is_owner(uid) or is_super_admin(uid, d)):
            await cq.answer("🚫 Owner/Super Admin only!", show_alert=True)
            return
        await state.set_state(W.fj_add)
        await sedit(
            cq,
            "📢 <b>Add Force Join — Step 1/3</b>\n\n"
            "Channel/Group ka <b>link</b> bhejo:\n\n"
            "• <code>https://t.me/CIPHER889988</code>\n"
            "• <code>https://t.me/+eTVZFP92jkU1NGNl</code>\n"
            "• <code>@username</code>",
            kb([("❌ Cancel", "fj:menu")]),
        )

    elif c.startswith("fj:del:"):
        if not (is_owner(uid) or is_super_admin(uid, d)):
            await cq.answer("🚫 Owner/Super Admin only!", show_alert=True)
            return
        cid_str = c.split("fj:del:", 1)[1]
        d2 = load()
        d2["force_join"] = [x for x in d2.get("force_join", []) if str(x["id"]) != cid_str]
        save(d2)
        await cq.answer("🗑 Removed.")
        await sedit(cq, "📢 <b>Force Join Channels</b>", fj_menu_kb(uid, d2))

    elif c == "noop":
        pass

    await cq.answer()


# ══════════════════════════════════════════════
#  SMS SOURCE — dispatch to matching users
# ══════════════════════════════════════════════
async def _dispatch_sms_to_users(bot: Bot, source_chat_id, source_username, text, source_kind):
    to, sms = parse_sms(text)
    if not to or not sms:
        return 0, None

    d = load()
    matched = 0
    for uid_str, u in d.get("users", {}).items():
        ac = u.get("active", {})
        if not u.get("monitoring"):
            continue

        saved = str(ac.get("ch_id", "")).strip()
        saved_un = (source_username or "").strip().lstrip("@")

        hit = False
        if saved and source_chat_id is not None and str(saved) == str(source_chat_id):
            hit = True
        elif saved and saved.lstrip("@").lower() == saved_un.lower() and saved_un:
            hit = True
        elif not saved:
            hit = True

        if not hit:
            accept = [str(x).lstrip("@").lower() for x in u.get("accept_from", [])]
            if accept:
                if str(source_chat_id) in accept or saved_un.lower() in accept:
                    hit = True

        if not hit:
            continue

        matched += 1
        log.info(f"SMS_SOURCE kind={source_kind} uid={uid_str} -> dispatch to={to!r}")
        asyncio.create_task(_do_send(bot, int(uid_str), to, sms))

    return matched, (to, sms)


@R.channel_post()
async def channel_post_handler(msg: Message):
    chat = msg.chat
    text = (msg.text or msg.caption or "").strip()
    log.info(f"CHANNEL_POST chat_id={chat.id} type={chat.type} len={len(text)}")
    if not text:
        return
    n, parsed = await _dispatch_sms_to_users(
        msg.bot, chat.id, chat.username, text, "channel"
    )
    if parsed and n == 0:
        log.info(f"CHANNEL_POST no matching user for chat_id={chat.id}")


@R.edited_channel_post()
async def edited_channel_post_handler(msg: Message):
    chat = msg.chat
    text = (msg.text or msg.caption or "").strip()
    if not text:
        return
    await _dispatch_sms_to_users(msg.bot, chat.id, chat.username, text, "channel")


# ══════════════════════════════════════════════
#  PASTE + FORWARD HANDLER — private DM
# ══════════════════════════════════════════════
@R.message(F.chat.type == "private", ~F.text.startswith("/"))
async def private_dm_handler(msg: Message, state: FSMContext):
    """
    Any non-command text in bot DM.
    Requires: active combo (fb_url + device_id) present.
    Paste mode toggle gates pasted messages; forwards are always allowed.
    """
    current_state = await state.get_state()
    if current_state is not None:
        return

    uid = msg.from_user.id
    d = load()
    if not can_use(uid, d):
        return

    u = usr(uid, d)
    text = (msg.text or msg.caption or "").strip()
    if not text:
        return

    src_label = "paste"
    origin = getattr(msg, "forward_origin", None)
    if origin is not None or getattr(msg, "forward_from_chat", None) is not None:
        src_label = "forward"

    ac = u.get("active", {})
    if not ac.get("fb_url") or not ac.get("device_id"):
        to_check, sms_check = parse_sms(text)
        if to_check and sms_check:
            await safe_send(
                msg.bot,
                uid,
                "❌ Setup incomplete.\n\n"
                "🧙 Setup Wizard → Firebase → Device → SIM bharo.\n"
                "Uske baad DM mein paste/forward kar ke SMS bhej sakte ho.",
                parse_mode="HTML",
            )
        else:
            log.info(f"DM uid={uid} — no parse, no setup, ignoring")
        return

    if src_label == "paste" and not u.get("paste_mode", True):
        to_check, sms_check = parse_sms(text)
        if to_check and sms_check:
            await safe_send(
                msg.bot,
                uid,
                "🔴 Paste mode OFF hai.\n\n"
                "Menu → 📋 Paste ON karke try karo,\n"
                "ya message ko <b>forward</b> karo.",
                parse_mode="HTML",
            )
        return

    to, sms = parse_sms(text)
    if not to or not sms:
        log.info(f"DM_HANDLER uid={uid} kind={src_label} — parse failed, ignore")
        return

    log.info(f"DM_HANDLER uid={uid} kind={src_label} to={to!r} msg={sms[:40]!r} — sending")
    await safe_send(
        msg.bot,
        uid,
        f"📤 <b>Message received</b>\n\n"
        f"  📞 To      : <code>{to}</code>\n"
        f"  💬 Message : <code>{sms[:55]}</code>\n"
        f"  🕐 Sending now…",
        parse_mode="HTML",
    )
    asyncio.create_task(_do_send(msg.bot, uid, to, sms))


@R.message(F.chat.type.in_({"group", "supergroup"}))
async def group_handler(msg: Message, state: FSMContext):
    text = (msg.text or msg.caption or "").strip()
    if not text:
        return
    if text.startswith("/"):
        return
    if msg.from_user and msg.from_user.is_bot:
        return

    chat = msg.chat
    n, parsed = await _dispatch_sms_to_users(
        msg.bot, chat.id, chat.username, text, "group"
    )
    if parsed and n > 0:
        log.info(f"GROUP_POST matched {n} users chat_id={chat.id}")


# ══════════════════════════════════════════════
#  APK SCANNER
# ══════════════════════════════════════════════
def _ax_str(data):
    r = []
    c = []
    for b in data:
        if 32 <= b <= 126:
            c.append(chr(b))
        else:
            if len(c) >= 6:
                r.append("".join(c))
            c = []
    if len(c) >= 6:
        r.append("".join(c))
    return "\n".join(r)


def scan_apk(path):
    _PATS = {
        "DB": r"https://[a-zA-Z0-9-]+\.firebaseio\.com",
        "AK": r"AIza[0-9A-Za-z\-_]",
    }
    res = {k: "-" for k in _PATS}
    chunks = []
    rb = b""
    try:
        with open(path, "rb") as f:
            rb = f.read()
    except OSError as e:
        log.error(f"scan_apk read {path}: {e}")
        return res
    if rb:
        chunks.append(_ax_str(rb))
    try:
        with zipfile.ZipFile(io.BytesIO(rb), "r") as z:
            for n in z.namelist():
                try:
                    chunks.append(z.read(n).decode("utf-8", "ignore"))
                except Exception:
                    pass
    except zipfile.BadZipFile as e:
        log.warning(f"scan_apk {path}: not a valid zip ({e})")
    combined = "\n".join(chunks)
    for k, v in _PATS.items():
        m = re.search(v, combined)
        if m:
            res[k] = m.group(0)
    return res


# ══════════════════════════════════════════════
#  HTTP HEALTH SERVER — optional, port-safe
# ══════════════════════════════════════════════
async def _health(request):
    return web.Response(text="ok", status=200)


async def _start_http_server():
    """
    Start HTTP health server for Render Web Service.
    Termux/local pe port busy ho to silently skip — bot is not affected.
    Set ENABLE_HTTP=0 to skip entirely.
    """
    if not _ENABLE_HTTP:
        log.info("HTTP server disabled (ENABLE_HTTP=0)")
        return
    try:
        app = web.Application()
        app.router.add_get("/", _health)
        app.router.add_get("/health", _health)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", _HTTP_PORT)
        await site.start()
        log.info(f"HTTP health server listening on 0.0.0.0:{_HTTP_PORT}")
    except OSError as e:
        log.warning(f"HTTP server skipped — port {_HTTP_PORT} busy ({e})")
    except Exception as e:
        log.warning(f"HTTP server failed to start ({e}) — continuing without it")


# ══════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════
async def main():
    await _start_http_server()

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(R)
    me = await bot.get_me()
    log.info(f"✅ @{me.username} started ({_VERSION}) | by {_CREDITS} | free mode ON")
    await safe_send(
        bot,
        _owner(),
        f"🚀 **SMS Bot {_VERSION} Online**\n"
        f"@{me.username}\n"
        f"<i>{_CREDITS}</i>\n"
        f"Free Mode: <b>ON</b>\n"
        f"`{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`",
        parse_mode="HTML",
    )
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())