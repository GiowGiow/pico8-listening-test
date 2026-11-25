import logging

from flask import Flask, jsonify

from .admin import admin
from .api import api
from .catalog import ensure_schema, load_catalog, sync_catalog
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
    app.config["CATALOG"] = catalog
    app.config["CATALOG_TAGS"] = catalog["tags"]
    app.config["AUDIO_IDS"] = frozenset(s["id"] for s in catalog["songs"])
    app.config["IMAGE_IDS"] = frozenset(p["image"] for p in catalog["pairs"])
    with app.app_context():
        ensure_schema()
        sync_catalog(catalog)

    app.register_blueprint(api)
    app.register_blueprint(admin)

    @app.errorhandler(404)
    def not_found(_exc):
        return jsonify({"error": "not_found"}), 404

    return app
