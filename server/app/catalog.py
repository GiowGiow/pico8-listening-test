"""The catalog: which clips and pairs exist and what each one is.

catalog/catalog.json is written by tools/prepare_pairs.py and shipped inside
the image next to the audio and image files. It is the only place that says
whether a clip is human or generated; the public API never returns that.
"""

import json
import logging

from sqlalchemy import inspect

from .db import db
from .models import Pair, Response, Song

log = logging.getLogger(__name__)


def load_catalog(path):
    with open(path, encoding="utf-8") as f:
        catalog = json.load(f)
    songs = {s["id"]: s for s in catalog["songs"]}
    for song in songs.values():
        if song["kind"] not in ("human", "genai"):
            raise ValueError(f"bad kind for {song['id']}")
    if not catalog.get("pairs"):
        raise ValueError("catalog has no pairs")
    for pair in catalog["pairs"]:
        if pair.get("role", "pool") not in ("pool", "anchor"):
            raise ValueError(f"bad role for pair {pair['id']}")
        if songs[pair["human"]]["kind"] != "human" or songs[pair["genai"]]["kind"] != "genai":
            raise ValueError(f"pair {pair['id']} must be one human and one generated clip")
    return catalog


def ensure_schema():
    """Create the tables; rebuild them if they come from an older layout.

    The first version of the study had no pair table. Rebuilding is only
    allowed while nobody has answered, so answers are never thrown away.
    """
    tables = set(inspect(db.engine).get_table_names())
    outdated = False
    if "response" in tables:
        columns = {c["name"] for c in inspect(db.engine).get_columns("response")}
        outdated = not {"pair_id", "question", "choice", "familiarity"} <= columns
    if outdated:
        answered = db.session.execute(
            db.text("select count(*) from response where answered_at is not null")
        ).scalar()
        if answered:
            raise RuntimeError("database has answers in an older layout; export them before upgrading")
        log.warning("database layout is outdated and has no answers: rebuilding it")
        db.drop_all()
        for table in ("response", "participant", "pair", "song"):
            db.session.execute(db.text(f"drop table if exists {table}"))
        db.session.commit()
    db.create_all()


def sync_catalog(catalog):
    """Insert new songs and pairs, refresh metadata, deactivate what left the catalog.

    Nothing is deleted, because answered responses point at songs and pairs,
    and assignment counts are kept across deploys.
    """
    wanted = {s["id"]: s for s in catalog["songs"]}
    existing = {s.id: s for s in Song.query.all()}
    for sid, spec in wanted.items():
        song = existing.get(sid)
        if song is None:
            song = Song(id=sid)
            db.session.add(song)
        song.system = spec["system"]
        song.kind = spec["kind"]
        song.source_id = spec["source_id"]
        song.active = True
    for sid, song in existing.items():
        if sid not in wanted:
            song.active = False

    wanted_pairs = {p["id"]: p for p in catalog["pairs"]}
    existing_pairs = {p.id: p for p in Pair.query.all()}
    added = 0
    for pid, spec in wanted_pairs.items():
        pair = existing_pairs.get(pid)
        if pair is None:
            pair = Pair(id=pid, count=0)
            db.session.add(pair)
            added += 1
        game = spec.get("game", {})
        pair.tag = spec["tag"]
        pair.role = spec.get("role", "pool")
        pair.human_id = spec["human"]
        pair.genai_id = spec["genai"]
        pair.image_id = spec["image"]
        pair.game_tid = str(game.get("tid", ""))
        pair.game_url = game.get("url")
        pair.license = game.get("license")
        pair.active = True
    for pid, pair in existing_pairs.items():
        if pid not in wanted_pairs:
            pair.active = False
    db.session.commit()
    log.info("catalog synced: %d songs, %d pairs (%d new)", len(wanted), len(wanted_pairs), added)
