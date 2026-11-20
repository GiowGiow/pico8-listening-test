import logging

from flask import Flask, jsonify

from .api import api
from .catalog import load_catalog, sync_catalog
from .config import load_config
from .db import db
from .limiter import limiter


def create_app(overrides=None):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    app = Flask(__name__)
    app.config.from_mapping(load_config())
    if overrides:
        app.config.update(overrides)

    app.config["DATA_DIR"].mkdir(parents=True, exist_ok=True)
    db.init_app(app)
    limiter.init_app(app)

    catalog = load_catalog(app.config["CATALOG_PATH"])
    app.config["CATALOG_SYSTEMS"] = catalog["systems"]
    app.config["AUDIO_IDS"] = frozenset(s["id"] for s in catalog["songs"])
    with app.app_context():
        db.create_all()
        sync_catalog(catalog)

    app.register_blueprint(api)

    @app.errorhandler(404)
    def not_found(_exc):
        return jsonify({"error": "not_found"}), 404

    return app
