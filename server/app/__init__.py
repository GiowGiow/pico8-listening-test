import logging

from flask import Flask, jsonify

from .admin import admin
from .api import api
from .config import load_config
from .db import db
from .limiter import limiter
from .scenarios import load_package, sync_scenarios


def create_app(overrides=None):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    app = Flask(__name__)
    app.config.from_mapping(load_config())
    if overrides:
        app.config.update(overrides)

    app.config["DATA_DIR"].mkdir(parents=True, exist_ok=True)
    db.init_app(app)
    limiter.init_app(app)

    study, scenarios = load_package(app.config["STUDY_DIR"])
    app.config["STUDY"] = study
    app.config["SCENARIOS"] = {s["external_id"]: s for s in scenarios}
    with app.app_context():
        db.create_all()
        sync_scenarios(scenarios)
    logging.getLogger(__name__).info("package loaded: %d scenarios", len(scenarios))

    app.register_blueprint(api)
    app.register_blueprint(admin)

    @app.errorhandler(404)
    def not_found(_exc):
        return jsonify({"error": "not_found"}), 404

    return app
