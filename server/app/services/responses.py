import uuid

from app.models import Response
from app.repository import db


def save_responses_on_table(selected_pairs, user_uuid):

    for pair in selected_pairs:
        response = Response(
            id=str(uuid.uuid4()),
            uuid=user_uuid,
            track_A=pair[0],
            track_B=pair[1],
            is_last_response=False
        )
        db.session.add(response)