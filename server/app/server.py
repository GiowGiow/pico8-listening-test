import json
import logging

from flask import Flask
from flask_cors import CORS

from app import routes
from app.repository import db, migrate
from app.config import DevelopmentConfig, ProductionConfig
import os

from app.services.populate import populate_song_and_pairs

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)
CORS(app)

# Load config
if os.getenv("FLASK_ENV") == "PRD":
    logging.info("Using ProductionConfig")
    app.config.from_object(ProductionConfig)
else:
    logging.info("Using DevelopmentConfig")
    app.config.from_object(DevelopmentConfig)

db.init_app(app)
migrate.init_app(app, db)

s3_bucket = app.config['S3_BUCKET']
s3_key = app.config['S3_KEY']
s3_region = app.config['S3_REGION']

app.config['SONGS_BASE_PATH_S3'] = 'audios/'

with app.app_context():
    logging.info("Initializing db")
    db.create_all()
    logging.info("Db ready")
routes.register_routes(app)


if __name__ == "__main__":
    app.run(port=5000, host="0.0.0.0")
