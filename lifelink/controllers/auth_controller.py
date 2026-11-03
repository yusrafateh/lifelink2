"""CONTROLLER: registration, login, profile (REST: /api/auth/*, /api/me)."""
from datetime import date

from flask import Blueprint, current_app, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from ..db import get_db
from ..models import user_model
from ..services import auth, matching

bp = Blueprint("auth", __name__, url_prefix="/api")


@bp.post("/auth/register")
def register():
    data = request.get_json(silent=True) or {}
    errors = matching.validate_registration(data)
    if errors:
        return jsonify(error=" ".join(errors), errors=errors), 400
    db = get_db()
    email = data["email"].strip().lower()
    if user_model.get_by_email(db, email):
        return jsonify(error="Email already registered."), 409
    blood_group = data.get("blood_group") if data["role"] == "donor" else None
    uid = user_model.create_user(
        db, data["name"].strip(), email, data["phone"].strip(),
        generate_password_hash(data["password"]),      # salted hash, never plain text
        data["role"], data["city"].strip(), blood_group)
    return jsonify(message="Registered successfully.", id=uid), 201


@bp.post("/auth/login")
def login():
    cfg = current_app.config
    ip = request.remote_addr or "unknown"
    if not auth.login_limiter.allow(ip, cfg["LOGIN_MAX_ATTEMPTS"], cfg["LOGIN_WINDOW_SECONDS"]):
        return jsonify(error="Too many login attempts. Try again in a minute."), 429
    data = request.get_json(silent=True) or {}
    user = user_model.get_by_email(get_db(), str(data.get("email", "")).strip().lower())
    # same message for unknown e-mail / wrong password (no user enumeration)
    if not user or not check_password_hash(user["password_hash"], str(data.get("password", ""))):
        return jsonify(error="Invalid email or password."), 401
    if not user["is_active"]:
        return jsonify(error="Account disabled by administrator."), 403
    return jsonify(token=auth.issue_token(user["id"], user["role"]),
                   user=user_model.public_view(user))


@bp.get("/me")
@auth.login_required()
def me():
    return jsonify(user_model.public_view(g.user))


@bp.put("/me")
@auth.login_required()
def update_me():
    data = request.get_json(silent=True) or {}
    fields = {}
    for key in ("name", "phone", "city"):
        if key in data:
            if not str(data[key]).strip():
                return jsonify(error=f"{key} cannot be empty."), 400
            fields[key] = str(data[key]).strip()
    if g.user["role"] == "donor":
        if "blood_group" in data:
            if data["blood_group"] not in matching.BLOOD_GROUPS:
                return jsonify(error="Invalid blood group."), 400
            fields["blood_group"] = data["blood_group"]
        if "available" in data:
            fields["available"] = 1 if data["available"] else 0
        if "last_donation" in data:
            try:
                value = data["last_donation"]
                if value:
                    if date.fromisoformat(value) > date.today():
                        raise ValueError
                fields["last_donation"] = value or None
            except (ValueError, TypeError):
                return jsonify(error="last_donation must be a past date (YYYY-MM-DD)."), 400
    user_model.update_profile(get_db(), g.user["id"], fields)
    return jsonify(user_model.public_view(user_model.get_by_id(get_db(), g.user["id"])))
