"""Central configuration. All secrets/settings come from environment variables
(12-factor style) so the same code runs locally and in the cloud."""
import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")
    DATABASE_PATH = os.environ.get("DATABASE_PATH", "lifelink.db")
    TOKEN_MAX_AGE = int(os.environ.get("TOKEN_MAX_AGE", 8 * 3600))   # 8 hours
    DONATION_GAP_DAYS = 90            # medical rule: min gap between donations
    WORKER_THREADS = int(os.environ.get("WORKER_THREADS", 3))
    NOTIFY_DELAY_SECONDS = float(os.environ.get("NOTIFY_DELAY_SECONDS", 1.0))
    LOGIN_MAX_ATTEMPTS = 5            # per IP per window (rate limiting)
    LOGIN_WINDOW_SECONDS = 60
    START_WORKERS = True
    TESTING = False
