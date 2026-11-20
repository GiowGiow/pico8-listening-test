"""Database models.

All timestamps are naive UTC. The original server declared
``default=datetime.now()``, which calls now() once at import time, so every row
got the moment the process started instead of the moment it was written. Here
every default is the function itself (``default=utcnow``), evaluated per row.
"""

import uuid
from datetime import datetime, timezone

from .db import db


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Song(db.Model):
    # Opaque public id; it is also the audio file name, so it must not reveal
    # whether the clip is human or generated.
    id = db.Column(db.String(32), primary_key=True)
    # "real" for human-composed songs, otherwise the generative system name.
    system = db.Column(db.String(64), nullable=False, index=True)
    kind = db.Column(db.String(8), nullable=False)  # "human" | "genai"
    role = db.Column(db.String(8), nullable=False, default="pool")  # "pool" | "anchor"
    source_id = db.Column(db.String(255), nullable=False)
    count = db.Column(db.Integer, nullable=False, default=0)
    active = db.Column(db.Boolean, nullable=False, default=True)


class Participant(db.Model):
    # HMAC of the normalized e-mail; the address itself is never stored.
    id = db.Column(db.String(36), primary_key=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    ui_locale = db.Column(db.String(8))
    age = db.Column(db.Integer)
    language = db.Column(db.String(32))
    practical_experience = db.Column(db.Integer)
    formal_experience = db.Column(db.Integer)
    knows_ai_music = db.Column(db.Boolean)
    chiptune_familiarity = db.Column(db.Integer)
    profile_completed_at = db.Column(db.DateTime)

    responses = db.relationship(
        "Response", back_populates="participant", order_by="Response.position", lazy="select"
    )


class Response(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    participant_id = db.Column(db.String(36), db.ForeignKey("participant.id"), nullable=False, index=True)
    position = db.Column(db.Integer, nullable=False)
    track_a_id = db.Column(db.String(32), db.ForeignKey("song.id"), nullable=False)
    track_b_id = db.Column(db.String(32), db.ForeignKey("song.id"), nullable=False)
    # Generative system of the pair, or "anchor" for the pair everyone hears.
    pair_kind = db.Column(db.String(64), nullable=False)

    # 0 none, 1 track 1 is AI, 2 track 2 is AI, 3 both, 4 cannot tell
    human_perception = db.Column(db.Integer)
    # 0 none, 1 recognizes track 1, 2 track 2, 3 both
    song_recognition = db.Column(db.Integer)
    comments = db.Column(db.Text)
    time_spent_ms = db.Column(db.Integer)
    listened_a_s = db.Column(db.Float)
    listened_b_s = db.Column(db.Float)

    assigned_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    answered_at = db.Column(db.DateTime)

    participant = db.relationship("Participant", back_populates="responses")
    track_a = db.relationship("Song", foreign_keys=[track_a_id])
    track_b = db.relationship("Song", foreign_keys=[track_b_id])

    __table_args__ = (db.UniqueConstraint("participant_id", "position", name="uq_response_position"),)

    @property
    def answered(self):
        return self.answered_at is not None
