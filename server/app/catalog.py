"""The song catalog: which clips exist and what each one is.

catalog/catalog.json is written by tools/prepare_songs.py and shipped inside
the image next to the audio files. It is the only place that says whether a
clip is human or generated; the API never returns that information.
"""

import json
import logging

from .db import db
from .models import Song

log = logging.getLogger(__name__)


def load_catalog(path):
    with open(path, encoding="utf-8") as f:
        catalog = json.load(f)
    systems = catalog.get("systems") or []
    if not systems:
        raise ValueError("catalog has no generative systems")
    for song in catalog["songs"]:
        if song["kind"] not in ("human", "genai"):
            raise ValueError(f"bad kind for {song['id']}")
        if song.get("role", "pool") not in ("pool", "anchor"):
            raise ValueError(f"bad role for {song['id']}")
    return catalog


def sync_catalog(catalog):
    """Insert new songs, refresh metadata, deactivate songs that left the catalog.

    Songs are never deleted, because answered responses point at them, and
    their evaluation counts are kept across deploys.
    """
    wanted = {s["id"]: s for s in catalog["songs"]}
    existing = {s.id: s for s in Song.query.all()}
    added = 0
    for sid, spec in wanted.items():
        song = existing.get(sid)
        if song is None:
            song = Song(id=sid, count=0)
            db.session.add(song)
            added += 1
        song.system = spec["system"]
        song.kind = spec["kind"]
        song.role = spec.get("role", "pool")
        song.source_id = spec["source_id"]
        song.active = True
    deactivated = 0
    for sid, song in existing.items():
        if sid not in wanted and song.active:
            song.active = False
            deactivated += 1
    db.session.commit()
    log.info("catalog synced: %d songs, %d new, %d deactivated", len(wanted), added, deactivated)
