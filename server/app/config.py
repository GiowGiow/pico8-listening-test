"""Configuration, read from the environment.

Every value has a development default except PARTICIPANT_ID_SECRET, which is
required when APP_ENV=production: it is the key that turns an e-mail address
into a participant id, so a default would make the ids reversible by anyone
who reads this file.
"""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUESTIONS = {"fit", "ai", "preference"}


def _int(name, default):
    return int(os.environ.get(name, str(default)))


def load_config():
    env = os.environ.get("APP_ENV", "development")
    data_dir = Path(os.environ.get("DATA_DIR", ROOT / "data"))
    secret = os.environ.get("PARTICIPANT_ID_SECRET", "")
    if env == "production" and len(secret) < 32:
        raise RuntimeError("PARTICIPANT_ID_SECRET must be set (32+ characters) in production")
    if not secret:
        secret = "development-only-secret-do-not-use-in-production"

    question = os.environ.get("STUDY_QUESTION", "fit")
    if question not in QUESTIONS:
        raise RuntimeError(f"STUDY_QUESTION must be one of {sorted(QUESTIONS)}")

    return {
        "APP_ENV": env,
        "DATA_DIR": data_dir,
        "CATALOG_PATH": Path(os.environ.get("CATALOG_PATH", ROOT / "catalog" / "catalog.json")),
        "AUDIO_DIR": Path(os.environ.get("AUDIO_DIR", ROOT / "catalog" / "audio")),
        "SQLALCHEMY_DATABASE_URI": os.environ.get(
            "DATABASE_URL", "sqlite:///" + str(data_dir / "survey.db")
        ),
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "PARTICIPANT_ID_SECRET": secret,
        "IMAGE_DIR": Path(os.environ.get("IMAGE_DIR", ROOT / "catalog" / "images")),
        # Pairs each participant hears per game tag, plus the anchor pair.
        "PAIRS_PER_TAG": _int("PAIRS_PER_TAG", 2),
        # The one question asked about every pair: "fit" (which song matches the
        # game), "ai" (which song is AI-generated) or "preference".
        "STUDY_QUESTION": question,
        # Host names allowed to open /admin, which shows the answer key. The
        # public host must never be listed here.
        "ADMIN_HOSTS": frozenset(
            h.strip().lower() for h in os.environ.get("ADMIN_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()
        ),
        # Hard cap on registrations, so a flood of fake e-mails cannot grow the
        # database without bound.
        "MAX_PARTICIPANTS": _int("MAX_PARTICIPANTS", 5000),
        # Requests carry a few small JSON fields; nothing legitimate is bigger.
        "MAX_CONTENT_LENGTH": 16 * 1024,
        "RATELIMIT_STORAGE_URI": os.environ.get("RATELIMIT_STORAGE_URI", "memory://"),
        "RATELIMIT_ENABLED": os.environ.get("RATELIMIT_ENABLED", "1") == "1",
        "RATELIMIT_HEADERS_ENABLED": True,
        "JSON_SORT_KEYS": False,
    }
