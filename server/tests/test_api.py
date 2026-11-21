import json
import time

import pytest

from app import create_app
from app.db import db
from app.models import Participant, Response, Song

SYSTEMS = ["lstm-grid_block", "lstm-nlm", "markov"]


def make_catalog(tmp_path, per_system=4, humans=12):
    audio = tmp_path / "audio"
    audio.mkdir()
    songs = []

    def add(sid, system, kind, role="pool"):
        songs.append({"id": sid, "system": system, "kind": kind, "role": role, "source_id": f"src-{sid}"})
        (audio / f"{sid}.mp3").write_bytes(b"ID3" + sid.encode() * 100)

    n = iter(range(10_000))
    for s in SYSTEMS:
        for i in range(per_system):
            add(f"clip{next(n):06d}", s, "genai")
    for i in range(humans):
        add(f"clip{next(n):06d}", "real", "human")
    add(f"clip{next(n):06d}", "real", "human", "anchor")
    add(f"clip{next(n):06d}", "markov", "genai", "anchor")
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps({"systems": SYSTEMS, "songs": songs}))
    return path, audio


@pytest.fixture
def app(tmp_path):
    catalog, audio = make_catalog(tmp_path)
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'test.db'}",
        "CATALOG_PATH": catalog,
        "AUDIO_DIR": audio,
        "DATA_DIR": tmp_path / "data",
        "RATELIMIT_ENABLED": False,
    })
    # create_app already read the catalog path from the overrides
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def register(client, email="ana@example.com"):
    r = client.post("/api/participants", json={"email": email})
    assert r.status_code == 200, r.get_json()
    return r.get_json()["participant_id"]


def answer(client, pid, rid, **overrides):
    payload = {"human_perception": 1, "song_recognition": 0, "comments": "", "time_spent_ms": 5000,
               "listened_a_s": 12.5, "listened_b_s": 20}
    payload.update(overrides)
    return client.post(f"/api/responses/{rid}", json=payload, headers={"X-Participant-Id": pid})


def test_participant_id_is_stable_and_not_the_email(client):
    a = register(client, "Ana@Example.com ")
    b = register(client, "ana@example.com")
    assert a == b
    assert "ana" not in a
    c = register(client, "joao@example.com")
    assert c != a


def test_rejects_bad_email(client):
    r = client.post("/api/participants", json={"email": "not-an-email"})
    assert r.status_code == 400
    assert r.get_json() == {"error": "invalid_field", "field": "email"}


def test_session_assigns_balanced_pairs_once(app, client):
    pid = register(client)
    first = client.get("/api/session", headers={"X-Participant-Id": pid}).get_json()
    second = client.get("/api/session", headers={"X-Participant-Id": pid}).get_json()
    assert [p["response_id"] for p in first["pairs"]] == [p["response_id"] for p in second["pairs"]]
    assert len(first["pairs"]) == 3 * len(SYSTEMS) + 1

    with app.app_context():
        rows = Response.query.filter_by(participant_id=pid).order_by(Response.position).all()
        kinds = [r.pair_kind for r in rows]
        assert kinds[-1] == "anchor"
        for s in SYSTEMS:
            assert kinds.count(s) == 3
        for r in rows[:-1]:
            assert {r.track_a.kind, r.track_b.kind} == {"human", "genai"}
            gen = r.track_a if r.track_a.kind == "genai" else r.track_b
            assert gen.system == r.pair_kind
        humans = [r.track_a_id if r.track_a.kind == "human" else r.track_b_id for r in rows[:-1]]
        assert len(set(humans)) == len(humans)


def test_counts_spread_over_catalog(app, client):
    for i in range(4):
        pid = register(client, f"p{i}@example.com")
        client.get("/api/session", headers={"X-Participant-Id": pid})
    with app.app_context():
        for s in SYSTEMS:
            counts = [x.count for x in Song.query.filter_by(system=s, role="pool")]
            assert max(counts) - min(counts) <= 1


def test_api_never_reveals_labels(client):
    pid = register(client)
    data = client.get("/api/session", headers={"X-Participant-Id": pid}).get_data(as_text=True)
    for word in ["human", "genai", "markov", "lstm", "real", "anchor"]:
        assert word not in data


def test_timestamps_are_per_row_not_process_start(app, client):
    pid = register(client)
    pairs = client.get("/api/session", headers={"X-Participant-Id": pid}).get_json()["pairs"]
    time.sleep(1.1)
    assert answer(client, pid, pairs[0]["response_id"]).status_code == 200
    time.sleep(1.1)
    assert answer(client, pid, pairs[1]["response_id"]).status_code == 200
    pid2 = register(client, "later@example.com")
    with app.app_context():
        r0, r1 = (db.session.get(Response, pairs[i]["response_id"]) for i in (0, 1))
        assert r0.answered_at > r0.assigned_at
        assert (r1.answered_at - r0.answered_at).total_seconds() >= 1
        p1, p2 = db.session.get(Participant, pid), db.session.get(Participant, pid2)
        assert (p2.created_at - p1.created_at).total_seconds() >= 2


def test_cannot_answer_someone_elses_pair(client):
    alice = register(client, "alice@example.com")
    bob = register(client, "bob@example.com")
    pair = client.get("/api/session", headers={"X-Participant-Id": alice}).get_json()["pairs"][0]
    client.get("/api/session", headers={"X-Participant-Id": bob})
    assert answer(client, bob, pair["response_id"]).status_code == 404
    assert answer(client, "00000000-0000-0000-0000-000000000000", pair["response_id"]).status_code == 401
    r = client.post(f"/api/responses/{pair['response_id']}", json={})
    assert r.status_code == 401


def test_answer_is_write_once_and_validated(client):
    pid = register(client)
    rid = client.get("/api/session", headers={"X-Participant-Id": pid}).get_json()["pairs"][0]["response_id"]
    assert answer(client, pid, rid, human_perception=9).status_code == 400
    assert answer(client, pid, rid, human_perception="1").status_code == 400
    assert answer(client, pid, rid, comments="x" * 2001).status_code == 400
    assert answer(client, pid, rid).status_code == 200
    r = answer(client, pid, rid, human_perception=2)
    assert r.status_code == 409


def test_profile_only_after_all_pairs(client):
    pid = register(client)
    pairs = client.get("/api/session", headers={"X-Participant-Id": pid}).get_json()["pairs"]
    profile = {"age": 25, "language": "portuguese", "formal_experience": 0, "practical_experience": 1,
               "chiptune_familiarity": 2, "knows_ai_music": True}
    h = {"X-Participant-Id": pid}
    assert client.put("/api/participants/me", json=profile, headers=h).status_code == 409
    for p in pairs:
        assert answer(client, pid, p["response_id"]).status_code == 200
    assert register(client) and client.post("/api/participants", json={"email": "ana@example.com"}).get_json()["status"] == "pending_profile"
    assert client.put("/api/participants/me", json={**profile, "age": 0}, headers=h).status_code == 400
    assert client.put("/api/participants/me", json={**profile, "language": "<script>"}, headers=h).status_code == 400
    assert client.put("/api/participants/me", json=profile, headers=h).status_code == 200
    assert client.put("/api/participants/me", json=profile, headers=h).status_code == 409
    assert client.post("/api/participants", json={"email": "ana@example.com"}).get_json()["status"] == "completed"


def test_audio_served_with_ranges_and_only_catalog_ids(client):
    r = client.get("/api/audio/clip000000.mp3", headers={"Range": "bytes=0-9"})
    assert r.status_code == 206
    assert r.headers["Content-Type"] == "audio/mpeg"
    assert len(r.data) == 10
    assert client.get("/api/audio/..%2Fcatalog.mp3").status_code == 404
    assert client.get("/api/audio/doesnotexist.mp3").status_code == 404


def test_errors_do_not_leak_details(client):
    r = client.post("/api/participants", data="{", content_type="application/json")
    assert r.status_code == 400
    assert r.get_json() == {"error": "invalid_field", "field": "body"}
    r = client.post("/api/participants", data="x" * 20000, content_type="application/json")
    assert r.status_code == 413


def test_study_full(app, client):
    app.config["MAX_PARTICIPANTS"] = 1
    register(client, "one@example.com")
    r = client.post("/api/participants", json={"email": "two@example.com"})
    assert r.status_code == 503
    register(client, "one@example.com")  # existing participants can still come back


def test_rate_limit_on_registration(tmp_path):
    catalog, audio = make_catalog(tmp_path)
    app = create_app({
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'rl.db'}",
        "CATALOG_PATH": catalog, "AUDIO_DIR": audio, "DATA_DIR": tmp_path / "data",
        "RATELIMIT_ENABLED": True,
    })
    c = app.test_client()
    codes = [c.post("/api/participants", json={"email": f"x{i}@example.com"},
                    headers={"CF-Connecting-IP": "203.0.113.9"}).status_code for i in range(7)]
    assert codes[:5] == [200] * 5
    assert codes[5] == 429
    other = c.post("/api/participants", json={"email": "y@example.com"}, headers={"CF-Connecting-IP": "203.0.113.10"})
    assert other.status_code == 200


def test_side_and_order_are_random(app, client):
    with app.app_context():
        app.config["MAX_PARTICIPANTS"] = 10_000
    genai_on_a, total, first_kinds = 0, 0, set()
    for i in range(60):
        pid = register(client, f"side{i}@example.com")
        client.get("/api/session", headers={"X-Participant-Id": pid})
        with app.app_context():
            rows = Response.query.filter_by(participant_id=pid).order_by(Response.position).all()
            first_kinds.add(rows[0].pair_kind)
            for r in rows[:-1]:
                total += 1
                genai_on_a += r.track_a.kind == "genai"
    assert 0.4 < genai_on_a / total < 0.6
    assert first_kinds == set(SYSTEMS)
