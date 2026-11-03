"""CONTROLLER: admin-only monitoring endpoints (/api/admin/*)."""
from flask import Blueprint, jsonify

from ..db import get_db
from ..models import request_model, user_model
from ..services import auth, worker

bp = Blueprint("admin", __name__, url_prefix="/api/admin")


@bp.get("/stats")
@auth.login_required("admin")
def stats():
    data = request_model.stats(get_db())
    data["active_worker_threads"] = worker.active_thread_count()
    return jsonify(data)


@bp.get("/users")
@auth.login_required("admin")
def users():
    return jsonify([dict(u) for u in user_model.list_users(get_db())])


@bp.get("/requests")
@auth.login_required("admin")
def all_requests():
    return jsonify([dict(r) for r in request_model.list_all(get_db())])


@bp.post("/users/<int:user_id>/toggle")
@auth.login_required("admin")
def toggle_user(user_id):
    db = get_db()
    user = user_model.get_by_id(db, user_id)
    if user is None or user["role"] == "admin":
        return jsonify(error="User not found."), 404
    user_model.set_active(db, user_id, not user["is_active"])
    return jsonify(message="User status changed.", is_active=not user["is_active"])
