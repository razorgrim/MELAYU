"""
AQW MELAYU Bot — Web Dashboard
Flask server with Discord OAuth2 authentication.
Run alongside the bot: python dashboard.py
"""

import os
import json
import requests
import pymysql
import pymysql.cursors
from datetime import datetime
from urllib.parse import urlencode
from flask import (
    Flask, render_template, redirect, url_for,
    session, request, jsonify
)
from dotenv import load_dotenv

load_dotenv()

# ── Config ──────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.getenv("DASHBOARD_SECRET_KEY", "change-me-to-random-string")

DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
DISCORD_REDIRECT_URI = os.getenv("DASHBOARD_REDIRECT_URI", "http://localhost:5000/callback")
DISCORD_API = "https://discord.com/api/v10"

DAILY_STATS_FILE = "data/daily_stats.json"

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", 3306)),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME"),
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
}


# ── Database Helpers ────────────────────────────────────
def get_db():
    return pymysql.connect(**DB_CONFIG)


def db_fetchall(query, args=None):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(query, args or ())
            return cur.fetchall()
    finally:
        conn.close()


def db_fetchone(query, args=None):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(query, args or ())
            return cur.fetchone()
    finally:
        conn.close()


def db_execute(query, args=None):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(query, args or ())
            conn.commit()
    finally:
        conn.close()


# ── Guild ID Helper ────────────────────────────────────
def get_guild_id():
    """Get the first guild_id from verification_config (primary guild)."""
    row = db_fetchone("SELECT guild_id FROM verification_config LIMIT 1")
    if row:
        return row["guild_id"]
    row = db_fetchone("SELECT guild_id FROM ticket_config LIMIT 1")
    if row:
        return row["guild_id"]
    return None


# ── Daily Stats ─────────────────────────────────────────
def load_daily_stats():
    try:
        with open(DAILY_STATS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


# ── Discord OAuth2 ──────────────────────────────────────
def discord_oauth_url():
    params = {
        "client_id": DISCORD_CLIENT_ID,
        "redirect_uri": DISCORD_REDIRECT_URI,
        "response_type": "code",
        "scope": "identify guilds guilds.members.read",
    }
    return f"{DISCORD_API}/oauth2/authorize?{urlencode(params)}"


def exchange_code(code):
    data = {
        "client_id": DISCORD_CLIENT_ID,
        "client_secret": DISCORD_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": DISCORD_REDIRECT_URI,
    }
    r = requests.post(f"{DISCORD_API}/oauth2/token", data=data)
    return r.json()


def get_discord_user(token):
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(f"{DISCORD_API}/users/@me", headers=headers)
    return r.json()


def get_user_guilds(token):
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(f"{DISCORD_API}/users/@me/guilds", headers=headers)
    return r.json()


def get_guild_member(token, guild_id):
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(
        f"{DISCORD_API}/users/@me/guilds/{guild_id}/member",
        headers=headers
    )
    if r.status_code == 200:
        return r.json()
    return None


def check_user_authorized(token, guild_id):
    """Check if user is officer or admin in the guild."""
    member = get_guild_member(token, guild_id)
    if not member:
        return False

    # Check if user has admin permission (bit 3 = 0x8)
    permissions = int(member.get("permissions", 0))
    if permissions & 0x8:
        return True

    # Check if user has the officer role
    user_roles = member.get("roles", [])
    ticket_config = db_fetchone(
        "SELECT officer_role_id FROM ticket_config WHERE guild_id = %s",
        (guild_id,)
    )
    helper_config = db_fetchone(
        "SELECT officer_role_id FROM helper_config WHERE guild_id = %s",
        (guild_id,)
    )

    officer_role_ids = set()
    if ticket_config:
        officer_role_ids.add(str(ticket_config["officer_role_id"]))
    if helper_config:
        officer_role_ids.add(str(helper_config["officer_role_id"]))

    for role_id in user_roles:
        if str(role_id) in officer_role_ids:
            return True

    return False


# ── Auth Middleware ──────────────────────────────────────
def login_required(f):
    from functools import wraps

    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)

    return decorated


# ── Routes: Auth ────────────────────────────────────────
@app.route("/login-page")
def login_page():
    return render_template("login.html")


@app.route("/login")
def login():
    return redirect(discord_oauth_url())


@app.route("/callback")
def callback():
    code = request.args.get("code")
    if not code:
        return render_template("login.html", error="No authorization code received.")

    token_data = exchange_code(code)
    access_token = token_data.get("access_token")
    if not access_token:
        return render_template("login.html", error="Failed to get access token from Discord.")

    user = get_discord_user(access_token)
    if "id" not in user:
        return render_template("login.html", error="Failed to get user info from Discord.")

    guild_id = get_guild_id()
    if not guild_id:
        return render_template("login.html", error="Bot has no configured guild. Run /ticketsetup or /verification_setup first.")

    if not check_user_authorized(access_token, guild_id):
        return render_template(
            "login.html",
            error="Access denied. You must be an Officer or Administrator in the server."
        )

    session["user"] = user
    session["token"] = access_token
    session["guild_id"] = guild_id
    return redirect(url_for("index"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_page"))


# ── Routes: Pages ───────────────────────────────────────
@app.route("/")
@login_required
def index():
    guild_id = session["guild_id"]

    verified = db_fetchone(
        "SELECT COUNT(*) AS cnt FROM verified_users WHERE guild_id = %s",
        (guild_id,)
    )
    active = db_fetchone(
        "SELECT COUNT(*) AS cnt FROM active_tickets WHERE guild_id = %s",
        (guild_id,)
    )
    total_pts = db_fetchone(
        "SELECT COALESCE(SUM(points), 0) AS total FROM helper_points WHERE guild_id = %s",
        (guild_id,)
    )
    helpers_total = db_fetchone(
        "SELECT COUNT(*) AS cnt FROM helper_points WHERE guild_id = %s AND points > 0",
        (guild_id,)
    )
    in_guild = db_fetchone(
        "SELECT COUNT(*) AS cnt FROM verified_users WHERE guild_id = %s AND in_target_guild = 1",
        (guild_id,)
    )
    apps_pending = db_fetchone(
        "SELECT COUNT(*) AS cnt FROM helper_applications WHERE guild_id = %s AND status = 'pending'",
        (guild_id,)
    )
    apps_accepted = db_fetchone(
        "SELECT COUNT(*) AS cnt FROM helper_applications WHERE guild_id = %s AND status = 'accepted'",
        (guild_id,)
    )
    apps_rejected = db_fetchone(
        "SELECT COUNT(*) AS cnt FROM helper_applications WHERE guild_id = %s AND status = 'rejected'",
        (guild_id,)
    )

    stats = {
        "verified_users": verified["cnt"] if verified else 0,
        "active_tickets": active["cnt"] if active else 0,
        "total_points": total_pts["total"] if total_pts else 0,
        "helpers_total": helpers_total["cnt"] if helpers_total else 0,
        "guild_members": in_guild["cnt"] if in_guild else 0,
        "apps_pending": apps_pending["cnt"] if apps_pending else 0,
        "apps_accepted": apps_accepted["cnt"] if apps_accepted else 0,
        "apps_rejected": apps_rejected["cnt"] if apps_rejected else 0,
    }

    today = datetime.now().strftime("%Y-%m-%d")
    all_stats = load_daily_stats()
    daily_stats = all_stats.get(today)

    return render_template(
        "dashboard.html",
        active_page="dashboard",
        user=session["user"],
        stats=stats,
        daily_stats=daily_stats,
        today=today,
    )


@app.route("/verified-users")
@login_required
def verified_users():
    guild_id = session["guild_id"]
    users = db_fetchall(
        "SELECT * FROM verified_users WHERE guild_id = %s ORDER BY verified_at DESC",
        (guild_id,)
    )
    return render_template(
        "verified_users.html",
        active_page="verified_users",
        user=session["user"],
        users=users,
    )


@app.route("/tickets")
@login_required
def tickets():
    guild_id = session["guild_id"]
    raw_tickets = db_fetchall(
        "SELECT * FROM active_tickets WHERE guild_id = %s ORDER BY created_at DESC",
        (guild_id,)
    )

    active_tickets = []
    for t in raw_tickets:
        helpers = db_fetchall(
            "SELECT COUNT(*) AS cnt FROM active_ticket_helpers WHERE ticket_id = %s",
            (t["id"],)
        )
        t["helper_count"] = helpers[0]["cnt"] if helpers else 0
        active_tickets.append(t)

    today = datetime.now().strftime("%Y-%m-%d")
    all_stats = load_daily_stats()
    daily_stats = all_stats.get(today)

    return render_template(
        "tickets.html",
        active_page="tickets",
        user=session["user"],
        active_tickets=active_tickets,
        daily_stats=daily_stats,
    )


@app.route("/leaderboard")
@login_required
def leaderboard():
    guild_id = session["guild_id"]
    entries = db_fetchall(
        "SELECT * FROM helper_points WHERE guild_id = %s ORDER BY points DESC",
        (guild_id,)
    )
    return render_template(
        "leaderboard.html",
        active_page="leaderboard",
        user=session["user"],
        entries=entries,
    )


@app.route("/helper-apps")
@login_required
def helper_apps():
    guild_id = session["guild_id"]
    apps = db_fetchall(
        "SELECT * FROM helper_applications WHERE guild_id = %s ORDER BY created_at DESC",
        (guild_id,)
    )

    for app_item in apps:
        try:
            app_item["answers_parsed"] = json.loads(app_item["answers"])
        except Exception:
            app_item["answers_parsed"] = {}

    return render_template(
        "helper_apps.html",
        active_page="helper_apps",
        user=session["user"],
        apps=apps,
    )


@app.route("/settings")
@login_required
def settings():
    guild_id = session["guild_id"]
    verification = db_fetchone(
        "SELECT * FROM verification_config WHERE guild_id = %s", (guild_id,)
    ) or {}
    ticket = db_fetchone(
        "SELECT * FROM ticket_config WHERE guild_id = %s", (guild_id,)
    ) or {}
    helper = db_fetchone(
        "SELECT * FROM helper_config WHERE guild_id = %s", (guild_id,)
    ) or {}
    boost = db_fetchone(
        "SELECT * FROM server_settings WHERE guild_id = %s", (guild_id,)
    ) or {}

    return render_template(
        "settings.html",
        active_page="settings",
        user=session["user"],
        verification=verification,
        ticket=ticket,
        helper=helper,
        boost=boost,
    )


# ── Routes: API (Settings Save) ────────────────────────
@app.route("/api/settings/verification", methods=["POST"])
@login_required
def api_save_verification():
    guild_id = session["guild_id"]
    data = request.json
    try:
        db_execute(
            """
            INSERT INTO verification_config
            (guild_id, aqw_guild_name, adventure_role_id, member_role_id, image_url)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                aqw_guild_name = VALUES(aqw_guild_name),
                adventure_role_id = VALUES(adventure_role_id),
                member_role_id = VALUES(member_role_id),
                image_url = VALUES(image_url)
            """,
            (
                guild_id,
                data.get("aqw_guild_name", ""),
                int(data.get("adventure_role_id", 0)),
                int(data.get("member_role_id", 0)),
                data.get("image_url", ""),
            ),
        )
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/settings/ticket", methods=["POST"])
@login_required
def api_save_ticket():
    guild_id = session["guild_id"]
    data = request.json
    try:
        db_execute(
            """
            INSERT INTO ticket_config
            (guild_id, officer_role_id, helper_role_id, bonus_role_id,
             ticket_category_id, ticket_log_channel_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                officer_role_id = VALUES(officer_role_id),
                helper_role_id = VALUES(helper_role_id),
                bonus_role_id = VALUES(bonus_role_id),
                ticket_category_id = VALUES(ticket_category_id),
                ticket_log_channel_id = VALUES(ticket_log_channel_id)
            """,
            (
                guild_id,
                int(data.get("officer_role_id", 0)),
                int(data.get("helper_role_id", 0)),
                int(data.get("bonus_role_id", 0)),
                int(data.get("ticket_category_id", 0)),
                int(data.get("ticket_log_channel_id", 0)),
            ),
        )
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/settings/helper", methods=["POST"])
@login_required
def api_save_helper():
    guild_id = session["guild_id"]
    data = request.json
    try:
        db_execute(
            """
            INSERT INTO helper_config
            (guild_id, officer_role_id, helper_role_id, review_category_id)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                officer_role_id = VALUES(officer_role_id),
                helper_role_id = VALUES(helper_role_id),
                review_category_id = VALUES(review_category_id)
            """,
            (
                guild_id,
                int(data.get("officer_role_id", 0)),
                int(data.get("helper_role_id", 0) or 0),
                int(data.get("review_category_id", 0) or 0),
            ),
        )
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/settings/boost", methods=["POST"])
@login_required
def api_save_boost():
    guild_id = session["guild_id"]
    data = request.json
    try:
        enabled = data.get("boost_notify_enabled", "0")
        if isinstance(enabled, str):
            enabled = enabled in ("1", "true", "True")

        db_execute(
            """
            INSERT INTO server_settings
            (guild_id, boost_channel_id, boost_notify_enabled)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE
                boost_channel_id = VALUES(boost_channel_id),
                boost_notify_enabled = VALUES(boost_notify_enabled)
            """,
            (
                guild_id,
                int(data.get("boost_channel_id", 0) or 0),
                enabled,
            ),
        )
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ── Main ────────────────────────────────────────────────
if __name__ == "__main__":
    debug = os.getenv("DASHBOARD_DEBUG", "true").lower() == "true"
    port = int(os.getenv("DASHBOARD_PORT", 5000))
    print(f"[DASHBOARD] Starting web dashboard on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=debug)
