import logging
from uuid import UUID

from flask import Blueprint, jsonify, request

from app.models import Response
from app.repository import db

responses_bp = Blueprint('response', __name__, url_prefix='/response')
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

@responses_bp.route("/submit", methods=["POST"])
def submit_responses():
    data = request.get_json()
    headers = request.headers
    response_uuid = headers.get("x-response-uuid")
    res = data.get('response', {})
    time_spent = data.get('time', 0)

    try:
        response = Response.query.filter_by(
            id=response_uuid
        ).first()

        if not response:
            return jsonify({"error": "Response not found"}), 404

        # Check if response has already been submitted
        if response.is_completed():
            return jsonify({"message": "Response had already been submitted"}), 200

        response.human_perception = res.get('human_perception_option')
        response.song_recognition = res.get('song_recognition_option')
        response.comments = res.get('comments', '')
        response.is_last_response = res.get('is_last_response')
        response.time_spent = time_spent

        logging.info(f"Updating response: {response}")
        db.session.commit()
        return jsonify({"message": f"Response updated successfully"}), 200

    except Exception as e:
        db.session.rollback()
        logging.exception("Error while saving response", e)
        return jsonify({"error": "Failed to save response", "details": str(e)}), 400


@responses_bp.route("/<response_uuid>", methods=["GET"])
def get_response_by_uuid(response_uuid):
    try:
        response = Response.query.filter_by(id=response_uuid).first()
        if not response:
            return jsonify({"error": "Response not found"}), 404

        response_data = {
            "response_uuid": response.id,
            "user_uuid": response.uuid,
            "human_perception_option": response.human_perception,
            "song_recognition_option": response.song_recognition,
            "comments": response.comments,
        }

        return jsonify(response_data), 200

    except Exception as e:
        logging.exception("Error while fetching response", exc_info=True)
        return jsonify({"error": "Failed to fetch response", "details": str(e)}), 500