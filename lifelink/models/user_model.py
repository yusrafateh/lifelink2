"""MODEL: all SQL related to users. Only parameterised queries (no SQL injection)."""
from datetime import date, timedelta


def create_user(db, name, email, phone, password_hash, role, city, blood_group):
    cur = db.execute(
        "INSERT INTO users (name,email,phone,password_hash,role,city,blood_group) "
        "VALUES (?,?,?,?,?,?,?)",
        (name, email, phone, password_hash, role, city, blood_group),
    )
    db.commit()
    return cur.lastrowid


def get_by_email(db, email):
    return db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()


def get_by_id(db, user_id):
    return db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def update_profile(db, user_id, fields):
    allowed = {"name", "phone", "city", "blood_group", "available", "last_donation"}
    items = [(k, v) for k, v in fields.items() if k in allowed]
    if not items:
        return
    sets = ", ".join(f"{k} = ?" for k, _ in items)   # keys come from whitelist only
    db.execute(f"UPDATE users SET {sets} WHERE id = ?", [v for _, v in items] + [user_id])
    db.commit()


def find_eligible_donors(db, blood_groups, city, gap_days):
    """Donors in the same city, compatible group, available and rested."""
    cutoff = (date.today() - timedelta(days=gap_days)).isoformat()
    marks = ",".join("?" * len(blood_groups))
    return db.execute(
        f"SELECT * FROM users WHERE role='donor' AND is_active=1 AND available=1 "
        f"AND lower(city)=lower(?) AND blood_group IN ({marks}) "
        f"AND (last_donation IS NULL OR last_donation <= ?)",
        [city, *blood_groups, cutoff],
    ).fetchall()


def list_users(db):
    return db.execute(
        "SELECT id,name,email,phone,role,city,blood_group,available,is_active,created_at "
        "FROM users ORDER BY id"
    ).fetchall()


def set_active(db, user_id, active):
    db.execute("UPDATE users SET is_active=? WHERE id=? AND role!='admin'", (int(active), user_id))
    db.commit()


def public_view(row):
    """Never expose the password hash."""
    d = dict(row)
    d.pop("password_hash", None)
    return d
