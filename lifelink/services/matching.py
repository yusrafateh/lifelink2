"""SERVICE: pure business rules (no Flask, no DB) -> easy to test and reuse."""
import re

BLOOD_GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
URGENCY_LEVELS = ["normal", "urgent", "critical"]
URGENCY_PRIORITY = {"critical": 0, "urgent": 1, "normal": 2}   # lower = served first

# patient group -> donor groups that can safely give blood
COMPATIBLE_DONORS = {
    "A+":  ["A+", "A-", "O+", "O-"],
    "A-":  ["A-", "O-"],
    "B+":  ["B+", "B-", "O+", "O-"],
    "B-":  ["B-", "O-"],
    "AB+": ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"],
    "AB-": ["A-", "B-", "AB-", "O-"],
    "O+":  ["O+", "O-"],
    "O-":  ["O-"],
}

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^\+?[0-9\- ]{7,16}$")


def compatible_donor_groups(patient_group):
    return COMPATIBLE_DONORS.get(patient_group, [])


def build_message(req):
    return (f"[LifeLink {req['urgency'].upper()}] {req['units']} unit(s) of "
            f"{req['blood_group']} blood needed at {req['hospital']}, {req['city']}. "
            f"Open LifeLink to accept or decline.")


def validate_registration(data):
    """Returns a list of error strings (empty list = valid)."""
    errors = []
    if len(str(data.get("name", "")).strip()) < 2:
        errors.append("Name must have at least 2 characters.")
    if not EMAIL_RE.match(str(data.get("email", "")).strip()):
        errors.append("Valid email is required.")
    if not PHONE_RE.match(str(data.get("phone", "")).strip()):
        errors.append("Valid phone number is required.")
    if len(str(data.get("password", ""))) < 8:
        errors.append("Password must be at least 8 characters.")
    if data.get("role") not in ("donor", "requester"):
        errors.append("Role must be donor or requester.")
    if not str(data.get("city", "")).strip():
        errors.append("City is required.")
    if data.get("role") == "donor" and data.get("blood_group") not in BLOOD_GROUPS:
        errors.append("Donors must provide a valid blood group.")
    return errors


def validate_request(data):
    errors = []
    if len(str(data.get("patient_name", "")).strip()) < 2:
        errors.append("Patient name is required.")
    if data.get("blood_group") not in BLOOD_GROUPS:
        errors.append("Valid blood group is required.")
    try:
        units = int(data.get("units"))
        if not 1 <= units <= 10:
            raise ValueError
    except (TypeError, ValueError):
        errors.append("Units must be a number between 1 and 10.")
    if not str(data.get("city", "")).strip():
        errors.append("City is required.")
    if not str(data.get("hospital", "")).strip():
        errors.append("Hospital is required.")
    if data.get("urgency") not in URGENCY_LEVELS:
        errors.append("Urgency must be normal, urgent or critical.")
    return errors
