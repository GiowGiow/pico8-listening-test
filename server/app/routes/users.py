import logging

from flask import Blueprint, request, jsonify

from app.models import User
from app.repository import db

users_bp = Blueprint('users', __name__, url_prefix='/user')
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

@users_bp.route("/register", methods=["POST"])
def register_user():
    headers = request.headers
    uuid = headers.get("uuid")

    try:
        existing_user = User.query.filter_by(uuid=uuid).first()

        if existing_user and existing_user.has_completed_all_responses() and existing_user.has_been_fully_registered():
            return jsonify({"error": "User has already completed all responses"}), 403

        if existing_user:
            return jsonify({"message": "User already registered"}), 200

        new_user = User(uuid=uuid)
        db.session.add(new_user)
        db.session.commit()

        return jsonify({"message": "User registered successfully"}), 201

    except Exception as e:
        db.session.rollback()
        logging.exception("Error while registering user", exc_info=True)
        return jsonify({"error": "Failed to register user", "details": str(e)}), 400


@users_bp.route("/update", methods=["PUT"])
def update_user():
    headers = request.headers
    uuid = headers.get("uuid")
    user_data = request.get_json()

    try:
        existing_user = User.query.filter_by(uuid=uuid).first()

        if not existing_user:
            return jsonify({"error": "User not found"}), 404

        existing_user.language = user_data.get("language", existing_user.language)
        existing_user.age = user_data.get("age", existing_user.age)
        existing_user.practical_experience = user_data.get("practical_experience", existing_user.practical_experience)
        existing_user.formal_experience = user_data.get("formal_experience", existing_user.formal_experience)
        existing_user.knows_ai_music = user_data.get("knows_ai_music",existing_user.knows_ai_music)

        logging.info(f"Updating user {existing_user.uuid} : {user_data}")

        db.session.commit()

        return jsonify({"message": "User updated successfully"}), 200

    except Exception as e:
        db.session.rollback()
        logging.exception("Error while updating user", exc_info=True)
        return jsonify({"error": "Failed to update user", "details": str(e)}), 400
