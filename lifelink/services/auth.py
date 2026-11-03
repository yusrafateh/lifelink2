"""SERVICE: authentication & authorisation (signed tokens + role-based access)."""
import threading
import time
from functools import wraps

from flask import current_app, g, jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from ..db import get_db
from ..models import user_model


def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="lifelink-auth")


def issue_token(user_id, role):
    return _serializer().dumps({"uid": user_id, "role": role})


def login_required(*roles):
    """Decorator: valid Bearer token required; optional list of allowed roles (RBAC)."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            header = request.headers.get("Authorization", "")
            if not header.startswith("Bearer "):
                return jsonify(error="Authentication required."), 401
            try:
                payload = _serializer().loads(
                    header[7:], max_age=current_app.config["TOKEN_MAX_AGE"])
            except SignatureExpired:
                return jsonify(error="Token expired. Please log in again."), 401
            except BadSignature:
                return jsonify(error="Invalid token."), 401
            user = user_model.get_by_id(get_db(), payload["uid"])
            if user is None or not user["is_active"]:
                return jsonify(error="Account not found or disabled."), 401
            if roles and user["role"] not in roles:
                return jsonify(error="You do not have permission for this action."), 403
            g.user = user
            return fn(*args, **kwargs)
        return wrapper
    return decorator


class RateLimiter:
    """Tiny thread-safe in-memory limiter (protects login from brute force)."""

    def __init__(self):
        self._hits = {}
        self._lock = threading.Lock()

    def allow(self, key, limit, window):
        now = time.time()
        with self._lock:
            hits = [t for t in self._hits.get(key, []) if now - t < window]
            if len(hits) >= limit:
                self._hits[key] = hits
                return False
            hits.append(now)
            self._hits[key] = hits
            return True

    def reset(self):
        with self._lock:
            self._hits.clear()


login_limiter = RateLimiter()
