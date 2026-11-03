"""MODEL: notifications sent to donors (simulated SMS)."""


def create(db, request_id, donor_id, message):
    db.execute(
        "INSERT OR IGNORE INTO notifications (request_id,donor_id,message) VALUES (?,?,?)",
        (request_id, donor_id, message),
    )


def for_donor(db, donor_id):
    return db.execute(
        "SELECT n.id, n.request_id, n.message, n.status, n.created_at, r.status AS request_status, "
        "r.blood_group, r.hospital, r.city, r.urgency "
        "FROM notifications n JOIN blood_requests r ON r.id = n.request_id "
        "WHERE n.donor_id=? ORDER BY n.id DESC",
        (donor_id,),
    ).fetchall()


def get(db, notification_id):
    return db.execute("SELECT * FROM notifications WHERE id=?", (notification_id,)).fetchone()


def set_status(db, notification_id, status):
    db.execute("UPDATE notifications SET status=? WHERE id=?", (status, notification_id))
    db.commit()


def accepted_count(db, request_id):
    return db.execute(
        "SELECT COUNT(*) FROM notifications WHERE request_id=? AND status='accepted'", (request_id,)
    ).fetchone()[0]


def accepted_donors(db, request_id):
    """Contact details are revealed ONLY for donors who accepted (privacy)."""
    return db.execute(
        "SELECT u.name, u.phone, u.blood_group FROM notifications n "
        "JOIN users u ON u.id = n.donor_id WHERE n.request_id=? AND n.status='accepted'",
        (request_id,),
    ).fetchall()
