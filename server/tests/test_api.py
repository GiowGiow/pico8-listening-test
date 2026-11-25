import json
import time

import pytest

from app import create_app
from app.db import db
from app.models import Pair, Participant, Response

TAGS = ["platformer", "puzzle", "arcade"]


def make_catalog(tmp_path, per_tag=4):
    audio, images = tmp_path / "audio", tmp_path / "images"
    audio.mkdir()
    images.mkdir()
    songs, pairs = [], []
    n = iter(range(10_000))

    def add(system, kind, tag):
        sid = f"clip{next(n):06d}"
        songs.append({"id": sid, "system": system, "kind": kind, "tag": tag, "source_id": f"src-{sid}", "seconds": 20})
        (audio / f"{sid}.mp3").write_bytes(b"ID3" + sid.encode() * 100)
        return sid

    def pair(tag, role, system):
        pid = f"pair{next(n):06d}"
        image = f"img{next(n):06d}"
        (images / f"{image}.webp").write_bytes(b"RIFF" + image.encode())
        pairs.append({"id": pid, "tag": tag, "role": role, "human": add("real", "human", tag),
                      "genai": add(system, "genai", tag), "image": image,
                      "game": {"tid": str(next(n)), "url": "https://example.com", "license": "CC4-BY-NC-SA"}})

    for tag in TAGS:
        for _ in range(per_tag):
            pair(tag, "pool", "lstm-grid_block-tag")
    pair(TAGS[0], "anchor", "markov")
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps({"created_at": "2026-11-25", "clip_seconds": 20, "seed": 1, "tags": TAGS,
                                "generated": {"system": "lstm-grid_block-tag", "job": "1"},
                                "songs": songs, "pairs": pairs}))
    return path, audio


@pytest.fixture
def app(tmp_path):
    catalog, audio = make_catalog(tmp_path)
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'test.db'}",
        "CATALOG_PATH": catalog,
        "AUDIO_DIR": audio,
        "IMAGE_DIR": tmp_path / "images",
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
    payload = {"choice": 1, "familiarity": 0, "comments": "", "time_spent_ms": 5000,
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
    assert len(first["pairs"]) == 2 * len(TAGS) + 1
    assert {p["question"] for p in first["pairs"]} == {"fit"}
    assert client.get(first["pairs"][0]["image"]).status_code == 200

    with app.app_context():
        rows = Response.query.filter_by(participant_id=pid).order_by(Response.position).all()
        assert rows[-1].pair.role == "anchor"
        tags = [r.pair.tag for r in rows[:-1]]
        for t in TAGS:
            assert tags.count(t) == 2
        for r in rows:
            assert {r.track_a_id, r.track_b_id} == {r.pair.human_id, r.pair.genai_id}
        assert len({r.pair_id for r in rows}) == len(rows)


def test_counts_spread_over_catalog(app, client):
    for i in range(4):
        pid = register(client, f"p{i}@example.com")
        client.get("/api/session", headers={"X-Participant-Id": pid})
    with app.app_context():
        for t in TAGS:
            counts = [x.count for x in Pair.query.filter_by(tag=t, role="pool")]
            assert counts == [2] * 4


def test_question_is_configurable_and_stored(app, client):
    app.config["STUDY_QUESTION"] = "preference"
    pid = register(client)
    pairs = client.get("/api/session", headers={"X-Participant-Id": pid}).get_json()["pairs"]
    assert {p["question"] for p in pairs} == {"preference"}
    assert answer(client, pid, pairs[0]["response_id"], choice=2).status_code == 200
    with app.app_context():
        r = db.session.get(Response, pairs[0]["response_id"])
        assert r.question == "preference"
        assert r.chose_human == (r.track_b_id == r.pair.human_id)


def test_admin_only_on_internal_hosts(app, client):
    pid = register(client)
    pairs = client.get("/api/session", headers={"X-Participant-Id": pid}).get_json()["pairs"]
    for p in pairs:
        answer(client, pid, p["response_id"], comments="soa bem")
    assert client.get("/admin/", headers={"Host": "pico8-bh.giow.dev"}).status_code == 404
    assert client.get("/admin/", headers={"Host": "localhost", "X-Forwarded-Host": "pico8-bh.giow.dev"}).status_code == 404
    assert client.get("/admin/answers.csv", headers={"Host": "pico8-bh.giow.dev"}).status_code == 404
    r = client.get("/admin/", headers={"Host": "localhost"})
    assert r.status_code == 200
    page = r.get_data(as_text=True)
    assert "ERRO" not in page and "soa bem" in page
    csv = client.get("/admin/answers.csv", headers={"Host": "localhost"}).get_data(as_text=True)
    assert len(csv.strip().splitlines()) == len(pairs) + 1


def test_old_database_is_rebuilt_only_when_empty(tmp_path):
    import sqlite3
    catalog, audio = make_catalog(tmp_path)
    config = {"SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'old.db'}", "CATALOG_PATH": catalog,
              "AUDIO_DIR": audio, "IMAGE_DIR": tmp_path / "images", "DATA_DIR": tmp_path / "data",
              "RATELIMIT_ENABLED": False}
    con = sqlite3.connect(tmp_path / "old.db")
    con.execute("create table song (id text primary key, system text, kind text, role text, source_id text, count int, active int)")
    con.execute("create table response (id text primary key, participant_id text, answered_at text)")
    con.commit()
    create_app(config)  # empty: rebuilt
    con.execute("drop table response")
    con.execute("create table response (id text primary key, participant_id text, answered_at text)")
    con.execute("insert into response values ('r', 'p', '2026-11-21')")
    con.commit()
    with pytest.raises(RuntimeError):
        create_app(config)


def test_api_never_reveals_labels(client):
    pid = register(client)
    data = client.get("/api/session", headers={"X-Participant-Id": pid}).get_data(as_text=True)
    for word in ["human", "genai", "markov", "lstm", "real", "anchor", "src-", "example.com"]:
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
    assert answer(client, pid, rid, choice=3).status_code == 400
    assert answer(client, pid, rid, choice="1").status_code == 400
    assert answer(client, pid, rid, comments="x" * 2001).status_code == 400
    assert answer(client, pid, rid).status_code == 200
    r = answer(client, pid, rid, choice=2)
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
    r = client.get("/api/audio/clip000002.mp3", headers={"Range": "bytes=0-9"})
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
        "CATALOG_PATH": catalog, "AUDIO_DIR": audio, "IMAGE_DIR": tmp_path / "images",
        "DATA_DIR": tmp_path / "data", "RATELIMIT_ENABLED": True,
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
    genai_on_a, total, first_tags = 0, 0, set()
    for i in range(60):
        pid = register(client, f"side{i}@example.com")
        client.get("/api/session", headers={"X-Participant-Id": pid})
        with app.app_context():
            rows = Response.query.filter_by(participant_id=pid).order_by(Response.position).all()
            first_tags.add(rows[0].pair.tag)
            for r in rows[:-1]:
                total += 1
                genai_on_a += r.track_a_id == r.pair.genai_id
            assert rows[-1].track_a_id == rows[-1].pair.human_id
    assert 0.4 < genai_on_a / total < 0.6
    assert first_tags == set(TAGS)
