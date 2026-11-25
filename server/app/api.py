"""HTTP API, mounted under /api on the same origin as the web app (no CORS).

The participant id travels in the X-Participant-Id header. It is a 128-bit
HMAC of the e-mail, so it works as a bearer token: every endpoint that reads or
writes answers checks that the reservation belongs to that participant.
"""

import hashlib
import hmac
import logging
import math
import re

from flask import Blueprint, abort, current_app, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException

from . import questionnaire
from .db import db
from .limiter import limiter
from .models import Participant, Reservation, utcnow
from .scenarios import ID_RE, QUEUE_LOCK, SLOTS, complete, ensure_reservations

log = logging.getLogger(__name__)
api = Blueprint("api", __name__, url_prefix="/api")

EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")
LOCALES = {"pt-BR", "en"}
FILES = {"context.png": "image/png", **{f"{slot}.wav": "audio/wav" for slot in SLOTS}}


class BadRequest(Exception):
    def __init__(self, field):
        super().__init__(field)
        self.field = field


def error(status, code, **extra):
    return jsonify({"error": code, **extra}), status


def derive_participant_id(email):
    secret = current_app.config["PARTICIPANT_ID_SECRET"].encode()
    digest = hmac.new(secret, email.strip().lower().encode(), hashlib.sha256).hexdigest()
    return f"{digest[0:8]}-{digest[8:12]}-{digest[12:16]}-{digest[16:20]}-{digest[20:32]}"


def current_participant():
    pid = request.headers.get("X-Participant-Id", "")
    if not ID_RE.match(pid):
        abort(401)
    participant = db.session.get(Participant, pid)
    if participant is None:
        abort(401)
    return participant


def participant_status(participant, reservations=None):
    """pending_profile -> in_progress -> completed; study_full when no scenario is left."""
    if participant.finished_at is not None:
        return "completed"
    if participant.profile_completed_at is None:
        return "pending_profile"
    if reservations is not None and not reservations:
        return "study_full"
    return "in_progress"


def per_participant():
    return int(current_app.config["STUDY"]["scenarios_per_participant"])


# --- validation helpers -------------------------------------------------------

def body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise BadRequest("body")
    return data


def number_field(data, name, lo, hi, default=0.0):
    value = data.get(name, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise BadRequest(name)
    return float(min(max(value, lo), hi))


# --- endpoints ----------------------------------------------------------------

@api.get("/health")
@limiter.exempt
def health():
    return jsonify({"ok": True})


@api.get("/study")
@limiter.limit("120/minute")
def study():
    """Texts of the study, exactly as the research package gives them."""
    package = current_app.config["STUDY"]
    return jsonify({
        "heading": package["heading"],
        "question": package["question"],
        "scale": package["scale"],
        "scenarios_per_participant": per_participant(),
        "questionnaire": questionnaire.public(),
    })


@api.post("/participants")
@limiter.limit("5/minute;30/hour")
def register():
    data = body()
    email = data.get("email")
    if not isinstance(email, str) or len(email) > 254 or not EMAIL_RE.match(email.strip()):
        raise BadRequest("email")
    locale = data.get("locale") if data.get("locale") in LOCALES else None

    pid = derive_participant_id(email)
    participant = db.session.get(Participant, pid)
    if participant is None:
        if Participant.query.count() >= current_app.config["MAX_PARTICIPANTS"]:
            return error(503, "study_full")
        participant = Participant(id=pid, ui_locale=locale)
        db.session.add(participant)
        db.session.commit()
        log.info("participant registered %s", pid[:8])
    return jsonify({"participant_id": pid, "status": participant_status(participant)})


@api.put("/participants/me")
@limiter.limit("20/minute")
def update_profile():
    participant = current_participant()
    if participant.profile_completed_at is not None:
        return error(409, "already_answered")

    data = body()
    for name, codes in questionnaire.CODES.items():
        if data.get(name) not in codes:
            raise BadRequest(name)
    for name in questionnaire.CODES:
        setattr(participant, name, data[name])
    participant.questionnaire_version = questionnaire.VERSION
    if data.get("locale") in LOCALES:
        participant.ui_locale = data["locale"]
    participant.profile_completed_at = utcnow()
    db.session.commit()
    return jsonify({"ok": True, "status": participant_status(participant)})


@api.get("/session")
@limiter.limit("60/minute")
def session():
    participant = current_participant()
    if participant.profile_completed_at is None:
        return jsonify({"status": "pending_profile", "scenarios": []})

    with QUEUE_LOCK:
        reservations = ensure_reservations(participant, per_participant(), current_app.config["RESERVATION_MINUTES"])
    records = current_app.config["SCENARIOS"]
    return jsonify({
        "status": participant_status(participant, reservations),
        "scenarios": [
            {
                "reservation_id": r.id,
                "heading": records[r.scenario_id]["context_heading"],
                "description": records[r.scenario_id]["description"],
                "image": f"/api/scenarios/{r.scenario_id}/context.png",
                # Slots are served exactly as packaged: A is A.wav, and so on.
                "audios": {slot: f"/api/scenarios/{r.scenario_id}/{slot}.wav" for slot in SLOTS},
                "answered": r.state == "completed",
            }
            for r in reservations
        ],
    })


@api.post("/ratings/<reservation_id>")
@limiter.limit("60/minute")
def submit_ratings(reservation_id):
    participant = current_participant()
    if not ID_RE.match(reservation_id):
        abort(404)
    reservation = db.session.get(Reservation, reservation_id)
    if reservation is None or reservation.participant_id != participant.id:
        abort(404)

    data = body()
    ratings = data.get("ratings")
    if not isinstance(ratings, dict) or set(ratings) != set(SLOTS):
        raise BadRequest("ratings")
    for slot in SLOTS:
        value = ratings[slot]
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 5:
            raise BadRequest(f"ratings.{slot}")
    listened = data.get("listened", {})
    if not isinstance(listened, dict):
        raise BadRequest("listened")
    extra = {"time_spent_ms": int(number_field(data, "time_spent_ms", 0, 6 * 3600 * 1000))}
    for slot in SLOTS:
        extra[f"listened_{slot.lower()}_s"] = round(number_field(listened, slot, 0, 3600), 1)

    with QUEUE_LOCK:
        outcome = complete(reservation, ratings, extra)
        if outcome == "lost":
            return error(409, "reservation_lost")
        reservations = ensure_reservations(participant, per_participant(), current_app.config["RESERVATION_MINUTES"])
    if outcome == "ok":
        log.info("scenario rated %s by %s", reservation.scenario_id[:8], participant.id[:8])
    # A repeated request (lost reply, double click) gets the same answer as the
    # first one and changes nothing.
    return jsonify({"ok": True, "status": participant_status(participant, reservations)})


@api.get("/scenarios/<scenario_id>/<name>")
@limiter.limit("600/minute")
def scenario_file(scenario_id, name):
    if name not in FILES or scenario_id not in current_app.config["SCENARIOS"]:
        abort(404)
    response = send_from_directory(
        current_app.config["STUDY_DIR"] / "scenarios" / scenario_id, name, mimetype=FILES[name],
        conditional=True, max_age=7 * 24 * 3600,
    )
    response.headers["Cache-Control"] = "public, max-age=604800, immutable"
    return response


# --- errors -------------------------------------------------------------------

@api.errorhandler(BadRequest)
def bad_request(exc):
    return error(400, "invalid_field", field=exc.field)


@api.errorhandler(HTTPException)
def http_error(exc):
    codes = {401: "unknown_participant", 404: "not_found", 405: "method_not_allowed",
             413: "too_large", 429: "too_many_requests"}
    return error(exc.code or 500, codes.get(exc.code, "http_error"))


@api.errorhandler(Exception)
def unexpected(exc):
    db.session.rollback()
    log.exception("unhandled error")
    return error(500, "internal_error")
