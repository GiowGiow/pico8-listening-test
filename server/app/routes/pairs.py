import logging
import random
import uuid

from flask import Blueprint, jsonify, request

from app.models import ExperimentType, Response, User
from app.repository import db
from app.services.pairs import get_least_evaluated_pairs, get_random_pairs, get_default_pair
from app.services.populate import populate_song_and_pairs
from app.services.responses import save_responses_on_table
from app.services.s3 import generate_url

pairs_bp = Blueprint('pairs', __name__, url_prefix='/pairs')
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

@pairs_bp.route("/", methods=["GET"])
def get_pairs():

    headers = request.headers
    user_uuid = headers.get("uuid")
    if not user_uuid:
        return jsonify({"error": "UUID is missing"}), 400

    try:
        selected_pairs = []
        # Check if user exists and has completed all responses
        user = User.query.filter_by(uuid=user_uuid).first()

        # Check if the user exists in the Response table
        user_response = Response.query.filter_by(uuid=user_uuid).first()
        if not user_response:

            rq1_pairs = get_least_evaluated_pairs(ExperimentType.rq1, 2)
            random_pairs = get_random_pairs(ExperimentType.random, 2)
            selected_pairs = rq1_pairs + random_pairs

            random.shuffle(selected_pairs)
            for pair in selected_pairs:
                random.shuffle(pair)

            selected_pairs += get_default_pair()

            save_responses_on_table(selected_pairs, user_uuid)
            db.session.commit()

        else:
            logging.info(f'User {uuid} already had pairs')

            selected_pairs = [[response.track_A, response.track_B] for response in
                              Response.query.filter_by(uuid=user_uuid, human_perception=None).all()]


        formatted_pairs = []
        for pair in selected_pairs:
            track_a_key = pair[0]
            track_b_key = pair[1]

            response = Response.query.filter_by(
                uuid=user_uuid,
                track_A=track_a_key,
                track_B=track_b_key
            ).first()

            formatted_pairs.append({
                "trackA": generate_url(track_a_key),
                "trackB": generate_url(track_b_key),
                "response_uuid": response.id
            })

        logging.info(f'Selected pairs: {formatted_pairs}')
        return jsonify({"pairs": formatted_pairs}), 200

    except Exception as e:
        logging.error("Error while getting pair", exc_info=True)
        return jsonify({"error": "Could not get pair", "details": str(e)}), 500


@pairs_bp.route("/populate", methods=["PUT"])
def populate_songs_from_s3():

    try:
        populate_song_and_pairs()

        return jsonify({"success": True}), 200

    except Exception as e:
        logging.error("Error while populating songs", exc_info=True)
        return jsonify({"error": "Could not populate songs", "details": str(e)}), 500

