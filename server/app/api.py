"""HTTP API, mounted under /api on the same origin as the web app (no CORS).

The participant id travels in the X-Participant-Id header. It is a 128-bit
HMAC of the e-mail, so it works as a bearer token: every endpoint that reads or
writes answers checks that the response belongs to that participant.
"""

import hashlib
import hmac
import logging
import math
import re

from flask import Blueprint, abort, current_app, g, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException

from .assignment import ASSIGN_LOCK, assign_pairs
from .db import db
from .limiter import limiter
from .models import Participant, Response, Song, utcnow

log = logging.getLogger(__name__)
api = Blueprint("api", __name__, url_prefix="/api")

EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")
PARTICIPANT_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
UUID_RE = PARTICIPANT_RE
SONG_RE = re.compile(r"^[A-Za-z0-9_-]{8,32}$")

LANGUAGES = {
    "portuguese", "english", "spanish", "french", "german", "italian", "mandarin",
    "japanese", "korean", "hindi", "arabic", "russian", "other",
}
LOCALES = {"pt-BR", "en"}
MAX_COMMENT = 2000


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
    if not PARTICIPANT_RE.match(pid):
        abort(401)
    participant = db.session.get(Participant, pid)
    if participant is None:
        abort(401)
    g.participant = participant
    return participant


def participant_status(participant):
    responses = participant.responses
    if participant.profile_completed_at is not None:
        return "completed"
    if responses and all(r.answered for r in responses):
        return "pending_profile"
    return "in_progress" if responses else "new"


# --- validation helpers -------------------------------------------------------

def body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise BadRequest("body")
    return data


def int_field(data, name, lo, hi):
    value = data.get(name)
    if isinstance(value, bool) or not isinstance(value, int) or not lo <= value <= hi:
        raise BadRequest(name)
    return value


def number_field(data, name, lo, hi, default=0.0):
    value = data.get(name, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise BadRequest(name)
    return float(min(max(value, lo), hi))


def choice_field(data, name, choices):
    value = data.get(name)
    if value not in choices:
        raise BadRequest(name)
    return value


# --- endpoints ----------------------------------------------------------------

@api.get("/health")
@limiter.exempt
def health():
    return jsonify({"ok": True})


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


@api.get("/session")
@limiter.limit("60/minute")
def session():
    participant = current_participant()
    with ASSIGN_LOCK:
        responses = Response.query.filter_by(participant_id=participant.id).order_by(Response.position).all()
        if not responses and participant.profile_completed_at is None:
            responses = assign_pairs(
                participant, current_app.config["CATALOG_SYSTEMS"], current_app.config["PAIRS_PER_SYSTEM"]
            )
    return jsonify({
        "status": participant_status(participant),
        "pairs": [
            {
                "response_id": r.id,
                "position": r.position,
                "track_a": f"/api/audio/{r.track_a_id}.mp3",
                "track_b": f"/api/audio/{r.track_b_id}.mp3",
                "answered": r.answered,
            }
            for r in responses
        ],
    })


@api.post("/responses/<response_id>")
@limiter.limit("60/minute")
def submit_response(response_id):
    participant = current_participant()
    if not UUID_RE.match(response_id):
        abort(404)
    response = db.session.get(Response, response_id)
    if response is None or response.participant_id != participant.id:
        abort(404)
    if response.answered:
        return error(409, "already_answered")

    data = body()
    comments = data.get("comments", "")
    if not isinstance(comments, str) or len(comments) > MAX_COMMENT:
        raise BadRequest("comments")

    response.human_perception = int_field(data, "human_perception", 0, 4)
    response.song_recognition = int_field(data, "song_recognition", 0, 3)
    response.comments = comments.strip() or None
    response.time_spent_ms = int(number_field(data, "time_spent_ms", 0, 6 * 3600 * 1000))
    response.listened_a_s = round(number_field(data, "listened_a_s", 0, 3600), 1)
    response.listened_b_s = round(number_field(data, "listened_b_s", 0, 3600), 1)
    response.answered_at = utcnow()
    db.session.commit()
    return jsonify({"ok": True, "status": participant_status(participant)})


@api.put("/participants/me")
@limiter.limit("20/minute")
def update_profile():
    participant = current_participant()
    status = participant_status(participant)
    if status == "completed":
        return error(409, "already_completed")
    if status != "pending_profile":
        return error(409, "survey_not_finished")

    data = body()
    knows_ai_music = data.get("knows_ai_music")
    if not isinstance(knows_ai_music, bool):
        raise BadRequest("knows_ai_music")
    participant.age = int_field(data, "age", 1, 120)
    participant.language = choice_field(data, "language", LANGUAGES)
    participant.formal_experience = int_field(data, "formal_experience", 0, 3)
    participant.practical_experience = int_field(data, "practical_experience", 0, 3)
    participant.chiptune_familiarity = int_field(data, "chiptune_familiarity", 0, 3)
    participant.knows_ai_music = knows_ai_music
    if data.get("locale") in LOCALES:
        participant.ui_locale = data["locale"]
    participant.profile_completed_at = utcnow()
    db.session.commit()
    log.info("participant completed %s", participant.id[:8])
    return jsonify({"ok": True, "status": "completed"})


@api.get("/audio/<song_id>.mp3")
@limiter.limit("600/minute")
def audio(song_id):
    if not SONG_RE.match(song_id) or song_id not in current_app.config["AUDIO_IDS"]:
        abort(404)
    response = send_from_directory(
        current_app.config["AUDIO_DIR"], f"{song_id}.mp3", mimetype="audio/mpeg",
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
