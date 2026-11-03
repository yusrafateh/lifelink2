"""MODEL: blood requests."""


def create_request(db, requester_id, patient_name, blood_group, units, city, hospital, urgency):
    cur = db.execute(
        "INSERT INTO blood_requests (requester_id,patient_name,blood_group,units,city,hospital,urgency) "
        "VALUES (?,?,?,?,?,?,?)",
        (requester_id, patient_name, blood_group, units, city, hospital, urgency),
    )
    db.commit()
    return cur.lastrowid


def get(db, request_id):
    return db.execute("SELECT * FROM blood_requests WHERE id=?", (request_id,)).fetchone()


def list_for_requester(db, requester_id):
    return db.execute(
        "SELECT * FROM blood_requests WHERE requester_id=? ORDER BY id DESC", (requester_id,)
    ).fetchall()


def list_all(db):
    return db.execute("SELECT * FROM blood_requests ORDER BY id DESC").fetchall()


def list_pending(db):
    return db.execute(
        "SELECT id, urgency FROM blood_requests WHERE status IN ('pending','matching')"
    ).fetchall()


def set_status(db, request_id, status, notified_count=None):
    if notified_count is None:
        db.execute("UPDATE blood_requests SET status=? WHERE id=?", (status, request_id))
    else:
        db.execute(
            "UPDATE blood_requests SET status=?, notified_count=? WHERE id=?",
            (status, notified_count, request_id),
        )
    db.commit()


def stats(db):
    q = lambda sql: db.execute(sql).fetchone()[0]
    return {
        "total_users": q("SELECT COUNT(*) FROM users"),
        "donors": q("SELECT COUNT(*) FROM users WHERE role='donor'"),
        "requesters": q("SELECT COUNT(*) FROM users WHERE role='requester'"),
        "total_requests": q("SELECT COUNT(*) FROM blood_requests"),
        "open_requests": q("SELECT COUNT(*) FROM blood_requests WHERE status='open'"),
        "fulfilled_requests": q("SELECT COUNT(*) FROM blood_requests WHERE status='fulfilled'"),
        "notifications_sent": q("SELECT COUNT(*) FROM notifications"),
    }
