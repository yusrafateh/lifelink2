"""Creates demo data (admin, donors, requester) so the project can be shown instantly."""
from datetime import date, timedelta

from werkzeug.security import generate_password_hash

from lifelink.db import connect

DEMO_PASSWORD = "Password123"
RECENT = (date.today() - timedelta(days=10)).isoformat()   # donated 10 days ago -> NOT eligible


def seed_demo_data(app):
    db = connect(app.config["DATABASE_PATH"])
    if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] > 0:
        db.close()
        return
    h = generate_password_hash(DEMO_PASSWORD)
    rows = [
        ("System Admin", "admin@lifelink.pk", "03000000000", h, "admin", "Karachi", None, None),
        ("Ali Raza", "ali@demo.pk", "03001111111", h, "donor", "Karachi", "O+", None),
        ("Sara Khan", "sara@demo.pk", "03002222222", h, "donor", "Karachi", "O-", None),
        ("Bilal Ahmed", "bilal@demo.pk", "03003333333", h, "donor", "Karachi", "A+", None),
        ("Hina Malik", "hina@demo.pk", "03004444444", h, "donor", "Karachi", "B+", None),
        ("Usman Shah", "usman@demo.pk", "03005555555", h, "donor", "Khairpur", "O+", None),
        ("Recent Donor", "recent@demo.pk", "03006666666", h, "donor", "Karachi", "O+", RECENT),
        ("Dr. Ayesha (Hospital)", "ayesha@demo.pk", "03007777777", h, "requester", "Karachi", None, None),
    ]
    for r in rows:
        db.execute(
            "INSERT INTO users (name,email,phone,password_hash,role,city,blood_group,last_donation) "
            "VALUES (?,?,?,?,?,?,?,?)", r)
    db.commit()
    db.close()
