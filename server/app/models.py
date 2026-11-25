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
    source_id = db.Column(db.String(255), nullable=False)
    active = db.Column(db.Boolean, nullable=False, default=True)


class Pair(db.Model):
    """One game with its original song and one generated song for the same tag."""

    id = db.Column(db.String(32), primary_key=True)
    tag = db.Column(db.String(32), nullable=False, index=True)
    role = db.Column(db.String(8), nullable=False, default="pool")  # "pool" | "anchor"
    human_id = db.Column(db.String(32), db.ForeignKey("song.id"), nullable=False)
    genai_id = db.Column(db.String(32), db.ForeignKey("song.id"), nullable=False)
    # Opaque id of the cartridge image, also its file name.
    image_id = db.Column(db.String(32), nullable=False)
    game_tid = db.Column(db.String(32), nullable=False)
    game_url = db.Column(db.String(255))
    license = db.Column(db.String(64))
    count = db.Column(db.Integer, nullable=False, default=0)
    active = db.Column(db.Boolean, nullable=False, default=True)

    human = db.relationship("Song", foreign_keys=[human_id])
    genai = db.relationship("Song", foreign_keys=[genai_id])


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
    pair_id = db.Column(db.String(32), db.ForeignKey("pair.id"), nullable=False, index=True)
    track_a_id = db.Column(db.String(32), db.ForeignKey("song.id"), nullable=False)
    track_b_id = db.Column(db.String(32), db.ForeignKey("song.id"), nullable=False)
    # Question the participant was asked: "fit" | "ai" | "preference". Stored
    # per answer so a change of STUDY_QUESTION never mixes two questions.
    question = db.Column(db.String(16), nullable=False)

    # 1 = track 1, 2 = track 2
    choice = db.Column(db.Integer)
    # 0 knew nothing, 1 knew the game, 2 knew one of the songs, 3 both
    familiarity = db.Column(db.Integer)
    comments = db.Column(db.Text)
    time_spent_ms = db.Column(db.Integer)
    listened_a_s = db.Column(db.Float)
    listened_b_s = db.Column(db.Float)

    assigned_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    answered_at = db.Column(db.DateTime)

    participant = db.relationship("Participant", back_populates="responses")
    pair = db.relationship("Pair")
    track_a = db.relationship("Song", foreign_keys=[track_a_id])
    track_b = db.relationship("Song", foreign_keys=[track_b_id])

    __table_args__ = (db.UniqueConstraint("participant_id", "position", name="uq_response_position"),)

    @property
    def answered(self):
        return self.answered_at is not None

    @property
    def chose_human(self):
        if self.choice is None:
            return None
        chosen = self.track_a_id if self.choice == 1 else self.track_b_id
        return chosen == self.pair.human_id
