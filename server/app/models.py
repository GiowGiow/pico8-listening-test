import enum
import uuid
from datetime import datetime
import sqlalchemy.dialects.postgresql as pg

from app.repository import db

class SongType(str, enum.Enum):
    human = 'human'
    genai = 'genai'

class ExperimentType(str, enum.Enum):
    rq1 = 'rq1'
    random = 'random'
    default = 'default'

class Song(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(255), nullable=False)
    type = db.Column(db.Enum(SongType), nullable=False)
    experiment = db.Column(db.Enum(ExperimentType), nullable=False)
    count = db.Column(db.Integer, default=0)

class Pair(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    trackA_id = db.Column(db.String(36), db.ForeignKey('song.id'), nullable=False)
    trackB_id = db.Column(db.String(36), db.ForeignKey('song.id'), nullable=False)
    experiment = db.Column(db.Enum(ExperimentType), nullable=False)
    count = db.Column(db.Integer, default=0)

    # relationships
    trackA = db.relationship('Song', foreign_keys=[trackA_id])
    trackB = db.relationship('Song', foreign_keys=[trackB_id])


class Response(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    uuid = db.Column(db.String(36), nullable=False)
    track_A = db.Column(db.String(50))
    track_B = db.Column(db.String(50))
    human_perception = db.Column(db.Integer)
    song_recognition = db.Column(db.Integer)
    comments = db.Column(db.Text)
    is_last_response = db.Column(db.Boolean, default=False)
    time_spent = db.Column(db.Integer)
    timestamp = db.Column(db.DateTime, default=datetime.now())

    def __repr__(self):
        return (f"<Response(id={self.id}, "
                f"uuid={self.uuid}, "
                f"track_A={self.track_A}, "
                f"track_B={self.track_B}, "
                f"human_perception={self.human_perception}, "
                f"is_last_response={self.is_last_response}, "
                f"comments={self.comments}, "
                f"timestamp={self.timestamp})>")

    def is_completed(self):
        """Check if this response has been completed"""
        return self.human_perception is not None

class User(db.Model):
    uuid = db.Column(db.String(36), primary_key=True, unique=True)
    language = db.Column(db.String(36))
    age = db.Column(db.Integer)
    practical_experience = db.Column(db.Integer)
    formal_experience = db.Column(db.Integer)
    knows_ai_music = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f"User(uuid={self.uuid}, language={self.language}, age={self.age}, practical_experience={self.practical_experience}, formal_experience={self.formal_experience})"

    def has_completed_all_responses(self):
        """Check if user has completed all their assigned responses"""
        user_responses = Response.query.filter_by(uuid=self.uuid).all()
        if not user_responses:
            return False

        completed_responses = [r for r in user_responses if r.human_perception is not None]
        return len(completed_responses) == len(user_responses)

    def get_incomplete_responses(self):
        """Get list of incomplete responses for this user"""
        return Response.query.filter_by(uuid=self.uuid, human_perception=None).all()

    def can_submit_more_responses(self):
        """Check if user can submit more responses"""
        return len(self.get_incomplete_responses()) > 0

    def has_been_fully_registered(self):
        """Check if the user has been fully registered"""
        return self.language is not None and \
            self.practical_experience is not None and \
            self.formal_experience is not None and \
            self.age is not None