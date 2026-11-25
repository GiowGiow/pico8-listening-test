"""Database models. All timestamps are naive UTC."""

import uuid
from datetime import datetime, timezone

from .db import db


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Participant(db.Model):
    # HMAC of the normalized e-mail; the address itself is never stored.
    id = db.Column(db.String(36), primary_key=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    ui_locale = db.Column(db.String(8))

    # Opening questionnaire: option codes of app/questionnaire.py.
    age_range = db.Column(db.String(16))
    musical_experience = db.Column(db.String(16))
    gaming_frequency = db.Column(db.String(16))
    retro_familiarity = db.Column(db.String(16))
    region = db.Column(db.String(16))
    headphones = db.Column(db.String(8))
    questionnaire_version = db.Column(db.String(16))
    profile_completed_at = db.Column(db.DateTime)

    # Set when the participant has rated every scenario they were given.
    finished_at = db.Column(db.DateTime)

    reservations = db.relationship(
        "Reservation", back_populates="participant", order_by="Reservation.reserved_at", lazy="select"
    )


class Scenario(db.Model):
    """One game context of the research package, with its four clips A to D."""

    external_id = db.Column(db.String(36), primary_key=True)
    # collection_order_v2 of the package: the order scenarios are handed out.
    position = db.Column(db.Integer, nullable=False, unique=True)
    # The reservation that holds this scenario now. A scenario with a holder
    # whose time has not run out is not given to anyone else.
    holder_id = db.Column(db.String(36), index=True)
    # Set once, when its holder sends the four ratings; never handed out again.
    completed_at = db.Column(db.DateTime)


class Reservation(db.Model):
    """A scenario handed to one participant, and their four ratings once sent."""

    # The id doubles as the token the browser sends back with the ratings.
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    participant_id = db.Column(db.String(36), db.ForeignKey("participant.id"), nullable=False, index=True)
    scenario_id = db.Column(db.String(36), db.ForeignKey("scenario.external_id"), nullable=False, index=True)
    # "active" | "completed" | "lost" (ran out of time and the scenario went to someone else)
    state = db.Column(db.String(12), nullable=False, default="active")
    reserved_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    completed_at = db.Column(db.DateTime)

    # 1 (Não combina nada) to 5 (Combina muito bem), one per player.
    rating_a = db.Column(db.Integer)
    rating_b = db.Column(db.Integer)
    rating_c = db.Column(db.Integer)
    rating_d = db.Column(db.Integer)
    time_spent_ms = db.Column(db.Integer)
    listened_a_s = db.Column(db.Float)
    listened_b_s = db.Column(db.Float)
    listened_c_s = db.Column(db.Float)
    listened_d_s = db.Column(db.Float)

    participant = db.relationship("Participant", back_populates="reservations")
    scenario = db.relationship("Scenario")

    @property
    def ratings(self):
        return {"A": self.rating_a, "B": self.rating_b, "C": self.rating_c, "D": self.rating_d}
