"""Database layer: connection handling + schema (SQLite)."""
import sqlite3
from flask import g, current_app

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    phone TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('donor','requester','admin')),
    city TEXT NOT NULL,
    blood_group TEXT,
    available INTEGER NOT NULL DEFAULT 1,
    last_donation TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS blood_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    requester_id INTEGER NOT NULL REFERENCES users(id),
    patient_name TEXT NOT NULL,
    blood_group TEXT NOT NULL,
    units INTEGER NOT NULL CHECK (units BETWEEN 1 AND 10),
    city TEXT NOT NULL,
    hospital TEXT NOT NULL,
    urgency TEXT NOT NULL CHECK (urgency IN ('normal','urgent','critical')),
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','matching','open','fulfilled','cancelled')),
    notified_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER NOT NULL REFERENCES blood_requests(id),
    donor_id INTEGER NOT NULL REFERENCES users(id),
    message TEXT NOT NULL,
    channel TEXT NOT NULL DEFAULT 'sms-simulated',
    status TEXT NOT NULL DEFAULT 'sent' CHECK (status IN ('sent','accepted','declined')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (request_id, donor_id)
);
CREATE INDEX IF NOT EXISTS idx_users_match ON users(role, blood_group, city);
CREATE INDEX IF NOT EXISTS idx_req_status ON blood_requests(status);
"""


def connect(path):
    """Open a new connection. Each thread must use its own connection."""
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def get_db():
    """Per-request connection (stored in Flask's `g`)."""
    if "db" not in g:
        g.db = connect(current_app.config["DATABASE_PATH"])
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(path):
    conn = connect(path)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
