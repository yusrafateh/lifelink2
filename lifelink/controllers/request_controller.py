"""CONTROLLER: blood requests + donor notifications (REST: /api/requests, /api/notifications)."""
from flask import Blueprint, current_app, g, jsonify, request

from ..db import get_db
from ..models import notification_model, request_model
from ..services import auth, matching, worker

bp = Blueprint("requests", __name__, url_prefix="/api")


def _request_dict(db, row):
    d = dict(row)
    d["accepted_donors"] = [dict(x) for x in notification_model.accepted_donors(db, row["id"])]
    return d


@bp.post("/requests")
@auth.login_required("requester")
def create_request():
    data = request.get_json(silent=True) or {}
    errors = matching.validate_request(data)
    if errors:
        return jsonify(error=" ".join(errors), errors=errors), 400
    db = get_db()
    rid = request_model.create_request(
        db, g.user["id"], data["patient_name"].strip(), data["blood_group"],
        int(data["units"]), data["city"].strip(), data["hospital"].strip(), data["urgency"])
    if current_app.config["START_WORKERS"]:
        worker.enqueue(rid, data["urgency"])         # async: respond immediately
    return jsonify(message="Request received. Matching donors in background.", id=rid), 202


@bp.get("/requests/mine")
@auth.login_required("requester")
def my_requests():
    db = get_db()
    return jsonify([_request_dict(db, r) for r in request_model.list_for_requester(db, g.user["id"])])


@bp.post("/requests/<int:request_id>/cancel")
@auth.login_required("requester")
def cancel_request(request_id):
    db = get_db()
    row = request_model.get(db, request_id)
    if row is None or row["requester_id"] != g.user["id"]:     # ownership check
        return jsonify(error="Request not found."), 404
    if row["status"] in ("fulfilled", "cancelled"):
        return jsonify(error=f"Request already {row['status']}."), 409
    request_model.set_status(db, request_id, "cancelled")
    return jsonify(message="Request cancelled.")


@bp.get("/notifications")
@auth.login_required("donor")
def my_notifications():
    return jsonify([dict(r) for r in notification_model.for_donor(get_db(), g.user["id"])])


@bp.post("/notifications/<int:notification_id>/respond")
@auth.login_required("donor")
def respond(notification_id):
    data = request.get_json(silent=True) or {}
    answer = data.get("response")
    if answer not in ("accept", "decline"):
        return jsonify(error="response must be 'accept' or 'decline'."), 400
    db = get_db()
    note = notification_model.get(db, notification_id)
    if note is None or note["donor_id"] != g.user["id"]:
        return jsonify(error="Notification not found."), 404
    if note["status"] != "sent":
        return jsonify(error="You already responded."), 409
    req = request_model.get(db, note["request_id"])
    if req["status"] in ("cancelled", "fulfilled"):
        return jsonify(error=f"Request is already {req['status']}."), 409
    if answer == "decline":
        notification_model.set_status(db, notification_id, "declined")
        return jsonify(message="Declined.")
    notification_model.set_status(db, notification_id, "accepted")
    if notification_model.accepted_count(db, req["id"]) >= req["units"]:
        request_model.set_status(db, req["id"], "fulfilled")
    return jsonify(message="Thank you! The requester can now see your contact details.")
