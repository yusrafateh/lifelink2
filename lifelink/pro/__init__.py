"""LifeLink Pro - additive module (stock, camps, donor levels, leaderboard, donation
confirmation, audit log, multi-page dashboards).

It sits on top of the existing LifeLink API and does NOT modify the old controllers:
  * its own tables are prefixed  pro_  (created automatically in the same SQLite file)
  * authentication is delegated to the existing GET /api/me, so tokens/roles stay the same
  * the dashboards are served at  /pro
"""
import os
import sqlite3
from datetime import date, datetime, timedelta
from functools import wraps

from flask import Blueprint, current_app, g, jsonify, request, send_from_directory

STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
GROUPS = ["A+", "A-", "B+", "B-", "O+", "O-", "AB+", "AB-"]
GAP_DAYS = 90
LEVELS = [(10, "Platinum"), (6, "Gold"), (3, "Silver"), (0, "Bronze")]

bp = Blueprint("pro", __name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS pro_stock(
  blood_group TEXT PRIMARY KEY, units INTEGER NOT NULL CHECK(units >= 0));
CREATE TABLE IF NOT EXISTS pro_camps(
  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, city TEXT NOT NULL,
  camp_date TEXT NOT NULL, slots INTEGER NOT NULL CHECK(slots > 0));
CREATE TABLE IF NOT EXISTS pro_camp_regs(
  camp_id INTEGER NOT NULL, user_id INTEGER NOT NULL, UNIQUE(camp_id, user_id));
CREATE TABLE IF NOT EXISTS pro_donations(
  id INTEGER PRIMARY KEY AUTOINCREMENT, donor_id INTEGER NOT NULL, donor_name TEXT NOT NULL,
  blood_group TEXT NOT NULL, donated_on TEXT NOT NULL,
  place TEXT NOT NULL DEFAULT 'Self-reported', confirmed INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS ix_pro_don_donor ON pro_donations(donor_id, confirmed);
CREATE TABLE IF NOT EXISTS pro_audit(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS pro_daily(
  day TEXT PRIMARY KEY, requests INTEGER NOT NULL DEFAULT 0, donations INTEGER NOT NULL DEFAULT 0);
"""


# ---------------------------------------------------------------- database helpers
def _conn(path=None):
    c = sqlite3.connect(path or current_app.config["DATABASE_PATH"], timeout=10)
    c.row_factory = sqlite3.Row
    return c


def rows(sql, args=()):
    c = _conn()
    try:
        return [dict(r) for r in c.execute(sql, args).fetchall()]
    finally:
        c.close()


def one(sql, args=()):
    r = rows(sql, args)
    return r[0] if r else None


def scalar(sql, args=(), default=0):
    try:
        r = one(sql, args)
        return list(r.values())[0] if r else default
    except sqlite3.Error:
        return default


def write(fn):
    """Run fn(connection) in one transaction."""
    c = _conn()
    try:
        out = fn(c)
        c.commit()
        return out
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


def _audit(c, actor, action):
    c.execute("INSERT INTO pro_audit(ts,actor,action) VALUES (?,?,?)",
              (datetime.now().strftime("%Y-%m-%d %H:%M"), actor, action))


def _bump(c, field):
    assert field in ("requests", "donations")
    c.execute("INSERT OR IGNORE INTO pro_daily(day) VALUES (?)", (date.today().isoformat(),))
    c.execute(f"UPDATE pro_daily SET {field}={field}+1 WHERE day=?", (date.today().isoformat(),))


# ---------------------------------------------------------------- auth (delegated)
def whoami():
    """Ask the existing /api/me who the caller is, forwarding the same Authorization header."""
    h = request.headers.get("Authorization")
    if not h:
        return None
    try:
        with current_app.test_client() as c:
            r = c.get("/api/me", headers={"Authorization": h})
        if r.status_code != 200:
            return None
        j = r.get_json(silent=True) or {}
        u = j.get("user", j) if isinstance(j, dict) else {}
        return u if isinstance(u, dict) and u.get("id") else None
    except Exception:
        return None


def auth(*roles):
    def deco(f):
        @wraps(f)
        def w(*a, **k):
            u = whoami()
            if not u:
                return jsonify(error="Please log in again."), 401
            if roles and u.get("role") not in roles:
                return jsonify(error="You are not allowed to do this."), 403
            g.user = u
            return f(*a, **k)
        return w
    return deco


def _who(u):
    return f'{u.get("name", "user")} ({u.get("role", "?")})'


# ---------------------------------------------------------------- small business rules
def level_of(n):
    for need, name in LEVELS:
        if n >= need:
            return name


def next_level_at(n):
    for need, _ in reversed(LEVELS):
        if need > n:
            return need
    return None


def short_name(name):
    p = (name or "Donor").split()
    return p[0] if len(p) == 1 else f"{p[0]} {p[-1][0]}."


def _int(v, lo, hi, label):
    try:
        v = int(v)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a whole number.")
    if not lo <= v <= hi:
        raise ValueError(f"{label} must be between {lo} and {hi}.")
    return v


def _date(v, label):
    try:
        return date.fromisoformat(str(v))
    except ValueError:
        raise ValueError(f"{label} must be a date like 2026-11-20.")


@bp.errorhandler(ValueError)
def _bad(e):
    return jsonify(error=str(e)), 400


# ---------------------------------------------------------------- public endpoints
@bp.get("/api/pro/overview")
def overview():
    stock = {r["blood_group"]: r["units"] for r in rows("SELECT * FROM pro_stock")}
    days = [(date.today() - timedelta(days=i)) for i in range(6, -1, -1)]
    daily = {r["day"]: r for r in rows("SELECT * FROM pro_daily")}
    return jsonify(
        stock={k: stock.get(k, 0) for k in GROUPS},
        trend={"labels": [d.strftime("%a") for d in days],
               "requests": [daily.get(d.isoformat(), {}).get("requests", 0) for d in days],
               "donations": [daily.get(d.isoformat(), {}).get("donations", 0) for d in days]},
        totals={"donors": scalar("SELECT COUNT(*) FROM users WHERE role='donor'"),
                "open_requests": scalar("SELECT COUNT(*) FROM blood_requests "
                                        "WHERE status IN ('pending','matching','open')"),
                "units": scalar("SELECT COALESCE(SUM(units),0) FROM pro_stock"),
                "camps": scalar("SELECT COUNT(*) FROM pro_camps WHERE camp_date>=?",
                                (date.today().isoformat(),))},
        low_threshold=8)


@bp.get("/api/pro/leaderboard")
def leaderboard():
    out = rows("""SELECT d.donor_id, d.donor_name, d.blood_group, COUNT(*) AS n
                  FROM pro_donations d WHERE d.confirmed=1
                  GROUP BY d.donor_id ORDER BY n DESC, d.donor_name LIMIT 20""")
    return jsonify([{"rank": i + 1, "name": short_name(r["donor_name"]), "blood_group": r["blood_group"],
                     "donations": r["n"], "level": level_of(r["n"])} for i, r in enumerate(out)])


@bp.get("/api/pro/camps")
def camps_list():
    u = whoami()
    mine = set()
    if u:
        mine = {r["camp_id"] for r in rows("SELECT camp_id FROM pro_camp_regs WHERE user_id=?", (u["id"],))}
    out = rows("""SELECT c.*, (SELECT COUNT(*) FROM pro_camp_regs r WHERE r.camp_id=c.id) AS registered
                  FROM pro_camps c WHERE camp_date>=? ORDER BY camp_date""", (date.today().isoformat(),))
    for c in out:
        c["joined"] = c["id"] in mine
    return jsonify(out)


# ---------------------------------------------------------------- admin endpoints
@bp.post("/api/pro/stock")
@auth("admin")
def stock_adjust():
    b = request.get_json(silent=True) or {}
    grp = b.get("blood_group")
    if grp not in GROUPS:
        raise ValueError("Unknown blood group.")
    delta = _int(b.get("delta"), -50, 50, "Change")

    def tx(c):
        cur = c.execute("SELECT units FROM pro_stock WHERE blood_group=?", (grp,)).fetchone()
        now = (cur["units"] if cur else 0) + delta
        if now < 0:
            raise ValueError("Stock cannot go below zero.")
        c.execute("INSERT INTO pro_stock(blood_group,units) VALUES (?,?) "
                  "ON CONFLICT(blood_group) DO UPDATE SET units=excluded.units", (grp, now))
        _audit(c, _who(g.user), f"Adjusted {grp} stock by {delta:+d} (now {now})")
        return now
    return jsonify(blood_group=grp, units=write(tx))


@bp.post("/api/pro/camps")
@auth("admin")
def camp_create():
    b = request.get_json(silent=True) or {}
    name, city = str(b.get("name", "")).strip(), str(b.get("city", "")).strip()
    if len(name) < 3 or len(city) < 2:
        raise ValueError("Camp name and city are required.")
    d = _date(b.get("camp_date"), "Date")
    if d < date.today():
        raise ValueError("Camp date cannot be in the past.")
    slots = _int(b.get("slots"), 1, 1000, "Slots")

    def tx(c):
        cur = c.execute("INSERT INTO pro_camps(name,city,camp_date,slots) VALUES (?,?,?,?)",
                        (name[:80], city[:40], d.isoformat(), slots))
        _audit(c, _who(g.user), f"Created camp '{name[:80]}' in {city[:40]} on {d}")
        return cur.lastrowid
    return jsonify(id=write(tx)), 201


@bp.get("/api/pro/donations")
@auth("admin")
def donations_list():
    return jsonify(rows("SELECT * FROM pro_donations ORDER BY confirmed, donated_on DESC LIMIT 100"))


@bp.post("/api/pro/donations/<int:did>/confirm")
@auth("admin")
def donation_confirm(did):
    def tx(c):
        d = c.execute("SELECT * FROM pro_donations WHERE id=?", (did,)).fetchone()
        if not d:
            return None
        if d["confirmed"]:
            raise ValueError("This donation is already confirmed.")
        c.execute("UPDATE pro_donations SET confirmed=1 WHERE id=?", (did,))
        c.execute("INSERT INTO pro_stock(blood_group,units) VALUES (?,1) "
                  "ON CONFLICT(blood_group) DO UPDATE SET units=units+1", (d["blood_group"],))
        _bump(c, "donations")
        try:  # keep the 90-day matching rule of the original system up to date
            c.execute("UPDATE users SET last_donation=? WHERE id=?", (d["donated_on"], d["donor_id"]))
        except sqlite3.Error:
            pass
        _audit(c, _who(g.user), f'Confirmed donation of {d["donor_name"]} ({d["blood_group"]})')
        return True
    r = write(tx)
    if r is None:
        return jsonify(error="Donation not found."), 404
    return jsonify(ok=True)


@bp.get("/api/pro/audit")
@auth("admin")
def audit_list():
    return jsonify(rows("SELECT ts, actor, action FROM pro_audit ORDER BY id DESC LIMIT 100"))


# ---------------------------------------------------------------- donor endpoints
@bp.get("/api/pro/me")
@auth("donor")
def donor_me():
    uid = g.user["id"]
    hist = rows("SELECT id, donated_on, place, confirmed FROM pro_donations "
                "WHERE donor_id=? ORDER BY donated_on DESC", (uid,))
    done = [h for h in hist if h["confirmed"]]
    n = len(done)
    last = max((h["donated_on"] for h in done), default=None)
    nxt = (date.fromisoformat(last) + timedelta(days=GAP_DAYS)) if last else None
    return jsonify(
        name=g.user.get("name"), blood_group=g.user.get("blood_group"), count=n, level=level_of(n),
        next_at=next_level_at(n), last_donation=last,
        next_eligible=nxt.isoformat() if nxt else date.today().isoformat(),
        eligible=(nxt is None or nxt <= date.today()), history=hist)


@bp.post("/api/pro/donations")
@auth("donor")
def donation_log():
    b = request.get_json(silent=True) or {}
    d = _date(b.get("donated_on") or date.today().isoformat(), "Date")
    if d > date.today():
        raise ValueError("Donation date cannot be in the future.")
    if d < date.today() - timedelta(days=365):
        raise ValueError("Only donations from the last 12 months can be added.")
    place = (str(b.get("place", "")).strip() or "Self-reported")[:60]
    u = g.user
    if u.get("blood_group") not in GROUPS:
        raise ValueError("Your profile has no blood group yet.")
    last = scalar("SELECT MAX(donated_on) FROM pro_donations WHERE donor_id=?", (u["id"],), None)
    if last and abs((d - date.fromisoformat(last)).days) < GAP_DAYS:
        raise ValueError(f"Donations must be at least {GAP_DAYS} days apart (last one: {last}).")

    def tx(c):
        c.execute("INSERT INTO pro_donations(donor_id,donor_name,blood_group,donated_on,place) "
                  "VALUES (?,?,?,?,?)", (u["id"], u.get("name", "Donor"), u["blood_group"], d.isoformat(), place))
        _audit(c, _who(u), f"Submitted a donation for confirmation ({d})")
    write(tx)
    return jsonify(ok=True), 201


@bp.post("/api/pro/camps/<int:cid>/register")
@auth("donor")
def camp_register(cid):
    def tx(c):
        camp = c.execute("SELECT * FROM pro_camps WHERE id=?", (cid,)).fetchone()
        if not camp or camp["camp_date"] < date.today().isoformat():
            return "missing"
        if c.execute("SELECT 1 FROM pro_camp_regs WHERE camp_id=? AND user_id=?", (cid, g.user["id"])).fetchone():
            raise ValueError("You are already registered for this camp.")
        taken = c.execute("SELECT COUNT(*) FROM pro_camp_regs WHERE camp_id=?", (cid,)).fetchone()[0]
        if taken >= camp["slots"]:
            raise ValueError("This camp is full.")
        c.execute("INSERT INTO pro_camp_regs(camp_id,user_id) VALUES (?,?)", (cid, g.user["id"]))
        _audit(c, _who(g.user), f'Registered for camp \'{camp["name"]}\'')
        return "ok"
    if write(tx) == "missing":
        return jsonify(error="Camp not found."), 404
    return jsonify(ok=True), 201


# ---------------------------------------------------------------- audit hook for the OLD endpoints
def _audit_old_endpoints(resp):
    """Adds audit-log lines for the original controllers without editing them."""
    try:
        p = request.path
        if request.method != "POST" or resp.status_code not in (200, 201, 202) or not p.startswith("/api/"):
            return resp
        action = None
        if p == "/api/requests":
            action = "Created a blood request"
        elif p.startswith("/api/notifications/") and p.endswith("/respond"):
            action = f'Responded "{(request.get_json(silent=True) or {}).get("response", "?")}" to a matched request'
        elif p.startswith("/api/admin/users/") and p.endswith("/toggle"):
            action = "Enabled/disabled user account #" + p.split("/")[4]
        elif p.endswith("/cancel") and p.startswith("/api/requests/"):
            action = "Cancelled blood request #" + p.split("/")[3]
        if action:
            u = whoami()
            write(lambda c: (_audit(c, _who(u) if u else "unknown", action),
                             _bump(c, "requests") if p == "/api/requests" else None))
    except Exception:
        current_app.logger.exception("pro audit hook failed")
    return resp


# ---------------------------------------------------------------- UI
@bp.get("/pro")
def ui():
    return send_from_directory(STATIC, "pro.html", max_age=0)


@bp.get("/pro/assets/<path:name>")
def assets(name):
    return send_from_directory(STATIC, name, max_age=0)


# ---------------------------------------------------------------- setup + demo data
def _seed(path):
    c = _conn(path)
    try:
        c.executescript(SCHEMA)
        today = date.today()
        if c.execute("SELECT COUNT(*) FROM pro_stock").fetchone()[0] == 0:
            c.executemany("INSERT INTO pro_stock VALUES (?,?)",
                          [("A+", 18), ("A-", 5), ("B+", 22), ("B-", 4), ("O+", 27), ("O-", 6), ("AB+", 11), ("AB-", 3)])
        if c.execute("SELECT COUNT(*) FROM pro_daily").fetchone()[0] == 0:
            req, don = [4, 7, 5, 9, 6, 11, 8], [3, 5, 4, 6, 5, 8, 6]
            c.executemany("INSERT INTO pro_daily VALUES (?,?,?)",
                          [((today - timedelta(days=6 - i)).isoformat(), req[i], don[i]) for i in range(7)])
        if c.execute("SELECT COUNT(*) FROM pro_camps").fetchone()[0] == 0:
            c.executemany("INSERT INTO pro_camps(name,city,camp_date,slots) VALUES (?,?,?,?)", [
                ("MUET Campus Drive", "Khairpur", (today + timedelta(days=5)).isoformat(), 60),
                ("Civil Hospital Camp", "Karachi", (today + timedelta(days=9)).isoformat(), 40),
                ("Thalassemia Care Day", "Larkana", (today + timedelta(days=12)).isoformat(), 80),
                ("University Road Camp", "Karachi", (today + timedelta(days=18)).isoformat(), 100)])
        if c.execute("SELECT COUNT(*) FROM pro_donations").fetchone()[0] == 0:
            counts = {"usman@demo.pk": 10, "bilal@demo.pk": 6, "ali@demo.pk": 4, "sara@demo.pk": 3, "hina@demo.pk": 2}
            try:
                for email, n in counts.items():
                    u = c.execute("SELECT id,name,blood_group FROM users WHERE email=?", (email,)).fetchone()
                    if not u:
                        continue
                    for k in range(n):  # most recent one is 100 days ago -> donor is eligible again
                        c.execute("INSERT INTO pro_donations(donor_id,donor_name,blood_group,donated_on,place,confirmed) "
                                  "VALUES (?,?,?,?,?,1)",
                                  (u["id"], u["name"], u["blood_group"],
                                   (today - timedelta(days=100 + 110 * k)).isoformat(), "Blood camp"))
                # two fresh donations waiting for the admin to confirm (demo of the confirm flow)
                for email in ("hina@demo.pk", "sara@demo.pk"):
                    u = c.execute("SELECT id,name,blood_group FROM users WHERE email=?", (email,)).fetchone()
                    if u:
                        c.execute("INSERT INTO pro_donations(donor_id,donor_name,blood_group,donated_on,place,confirmed) "
                                  "VALUES (?,?,?,?,?,0)",
                                  (u["id"], u["name"], u["blood_group"], today.isoformat(), "Civil Hospital"))
            except sqlite3.Error:
                pass
        if c.execute("SELECT COUNT(*) FROM pro_audit").fetchone()[0] == 0:
            _audit(c, "system", "LifeLink Pro modules initialised")
        c.commit()
    finally:
        c.close()


def init_pro(app):
    """Call once, after create_app() and seed_demo_data()."""
    _seed(app.config["DATABASE_PATH"])
    app.register_blueprint(bp)
    app.after_request(_audit_old_endpoints)
