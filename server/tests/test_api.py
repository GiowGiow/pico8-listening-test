import json
import uuid
import wave
from datetime import timedelta

import pytest

from app import create_app, questionnaire
from app.db import db
from app.models import Participant, Reservation, Scenario, utcnow

SCALE = ["Não combina nada", "Combina pouco", "Mais ou menos", "Combina bem", "Combina muito bem"]
PROFILE = {"age_range": "25_34", "musical_experience": "hobby", "gaming_frequency": "weekly",
           "retro_familiarity": "some", "region": "sudeste", "headphones": "yes"}
RATINGS = {"A": 3, "B": 1, "C": 4, "D": 2}


def make_package(root, n=6):
    scenarios = []
    for order in range(n):
        eid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"scenario-{order}"))
        folder = root / "scenarios" / eid
        folder.mkdir(parents=True)
        (folder / "context.png").write_bytes(b"\x89PNG" + eid.encode())
        for slot in "ABCD":
            with wave.open(str(folder / f"{slot}.wav"), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(44100)
                w.writeframes(b"\0\0" * 4410)
        scenarios.append({
            "external_id": eid, "collection_order_v2": order, "context_heading": "Contexto do jogo",
            "description": f"Descrição {order}", "context_image": f"scenarios/{eid}/context.png",
            "audios": {slot: f"scenarios/{eid}/{slot}.wav" for slot in "ABCD"},
        })
    (root / "scenarios.json").write_text(json.dumps(scenarios))
    (root / "study.json").write_text(json.dumps({
        "heading": "Contexto do jogo", "question": "Quanto esta música combina com esse contexto?",
        "scale": [{"label": label, "value": i + 1} for i, label in enumerate(SCALE)],
        "scenarios_per_participant": 2, "demographics": {},
    }))
    return scenarios


@pytest.fixture
def package(tmp_path):
    return make_package(tmp_path / "study")


@pytest.fixture
def app(tmp_path, package):
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'test.db'}",
        "STUDY_DIR": tmp_path / "study",
        "RATELIMIT_ENABLED": False,
        "ADMIN_HOSTS": frozenset({"localhost"}),
    })
    yield app
    with app.app_context():
        db.session.remove()


@pytest.fixture
def client(app):
    return app.test_client()


def register(client, email="ana@example.com"):
    res = client.post("/api/participants", json={"email": email})
    assert res.status_code == 200
    return {"X-Participant-Id": res.get_json()["participant_id"]}


def start(client, email="ana@example.com"):
    """Register, answer the questionnaire and open the session."""
    headers = register(client, email)
    assert client.put("/api/participants/me", json=PROFILE, headers=headers).status_code == 200
    return headers, client.get("/api/session", headers=headers).get_json()


def rate(client, headers, scenario, ratings=RATINGS):
    return client.post(f"/api/ratings/{scenario['reservation_id']}", headers=headers,
                       json={"ratings": ratings, "time_spent_ms": 60000, "listened": {s: 30 for s in "ABCD"}})


def order_of(app, scenario):
    with app.app_context():
        return db.session.get(Reservation, scenario["reservation_id"]).scenario.position


def expire(app, scenario):
    with app.app_context():
        db.session.get(Reservation, scenario["reservation_id"]).expires_at = utcnow() - timedelta(minutes=1)
        db.session.commit()


def test_study_texts_come_from_the_package(client):
    study = client.get("/api/study").get_json()
    assert [s["label"] for s in study["scale"]] == SCALE
    assert [s["value"] for s in study["scale"]] == [1, 2, 3, 4, 5]
    assert study["scenarios_per_participant"] == 2
    assert [f["name"] for f in study["questionnaire"]["fields"]] == list(PROFILE)
    assert study["questionnaire"]["version"] == questionnaire.VERSION


def test_registration_is_stable_and_never_stores_the_email(client, app):
    a = register(client, "Ana@Example.com ")
    assert a == register(client, "ana@example.com")
    assert a != register(client, "bia@example.com")
    with app.app_context():
        assert "ana" not in db.session.get(Participant, a["X-Participant-Id"]).id


@pytest.mark.parametrize("email", ["", "not-an-email", "a@b", None, 5, "x" * 300 + "@example.com"])
def test_bad_email_is_rejected(client, email):
    assert client.post("/api/participants", json={"email": email}).status_code == 400


def test_endpoints_need_a_known_participant(client):
    assert client.get("/api/session").status_code == 401
    assert client.get("/api/session", headers={"X-Participant-Id": str(uuid.uuid4())}).status_code == 401
    assert client.put("/api/participants/me", json=PROFILE).status_code == 401


def test_questionnaire_comes_before_any_scenario(client, app):
    headers = register(client)
    session = client.get("/api/session", headers=headers).get_json()
    assert session == {"status": "pending_profile", "scenarios": []}
    with app.app_context():
        assert Reservation.query.count() == 0


@pytest.mark.parametrize("field,value", [("age_range", "30"), ("region", "Sudeste"), ("headphones", True),
                                         ("gaming_frequency", None), ("musical_experience", 2)])
def test_questionnaire_only_takes_listed_options(client, field, value):
    headers = register(client)
    assert client.put("/api/participants/me", json={**PROFILE, field: value}, headers=headers).status_code == 400
    missing = {k: v for k, v in PROFILE.items() if k != field}
    assert client.put("/api/participants/me", json=missing, headers=headers).status_code == 400


def test_questionnaire_is_stored_once(client, app):
    headers = register(client)
    assert client.put("/api/participants/me", json=PROFILE, headers=headers).get_json()["status"] == "in_progress"
    assert client.put("/api/participants/me", json={**PROFILE, "region": "sul"}, headers=headers).status_code == 409
    with app.app_context():
        p = db.session.get(Participant, headers["X-Participant-Id"])
        assert {name: getattr(p, name) for name in PROFILE} == PROFILE
        assert p.questionnaire_version == questionnaire.VERSION


def test_session_hands_out_the_next_two_scenarios_in_order(client, app, package):
    headers, session = start(client)
    assert session["status"] == "in_progress"
    assert [order_of(app, s) for s in session["scenarios"]] == [0, 1]
    first = session["scenarios"][0]
    eid = package[0]["external_id"]
    assert first["description"] == "Descrição 0" and first["heading"] == "Contexto do jogo"
    assert first["image"] == f"/api/scenarios/{eid}/context.png"
    assert first["audios"] == {slot: f"/api/scenarios/{eid}/{slot}.wav" for slot in "ABCD"}
    # asking again returns the same scenarios
    assert client.get("/api/session", headers=headers).get_json() == session


def test_two_participants_never_hold_the_same_scenario(client, app):
    _, a = start(client, "ana@example.com")
    _, b = start(client, "bia@example.com")
    assert [order_of(app, s) for s in a["scenarios"]] == [0, 1]
    assert [order_of(app, s) for s in b["scenarios"]] == [2, 3]


def test_ratings_are_stored_and_the_scenario_leaves_the_pool(client, app):
    headers, session = start(client)
    one, two = session["scenarios"]
    assert rate(client, headers, one).get_json() == {"ok": True, "status": "in_progress"}
    assert rate(client, headers, two, {"A": 5, "B": 5, "C": 1, "D": 2}).get_json()["status"] == "completed"
    with app.app_context():
        r = db.session.get(Reservation, one["reservation_id"])
        assert r.ratings == RATINGS and r.state == "completed" and r.time_spent_ms == 60000
        assert r.scenario.completed_at is not None
        assert db.session.get(Participant, headers["X-Participant-Id"]).finished_at is not None
    assert client.get("/api/session", headers=headers).get_json()["status"] == "completed"
    # the next participant starts after the two rated scenarios
    _, other = start(client, "bia@example.com")
    assert [order_of(app, s) for s in other["scenarios"]] == [2, 3]


def test_sending_ratings_twice_changes_nothing(client, app):
    headers, session = start(client)
    one = session["scenarios"][0]
    assert rate(client, headers, one).status_code == 200
    again = rate(client, headers, one, {"A": 1, "B": 1, "C": 1, "D": 1})
    assert again.status_code == 200 and again.get_json()["ok"] is True
    with app.app_context():
        assert db.session.get(Reservation, one["reservation_id"]).ratings == RATINGS
        assert Reservation.query.filter_by(state="completed").count() == 1


@pytest.mark.parametrize("ratings", [
    {"A": 3, "B": 1, "C": 4}, {"A": 0, "B": 1, "C": 4, "D": 2}, {"A": 6, "B": 1, "C": 4, "D": 2},
    {"A": "3", "B": 1, "C": 4, "D": 2}, {"A": 2.5, "B": 1, "C": 4, "D": 2}, {"A": True, "B": 1, "C": 4, "D": 2},
    {"A": 3, "B": 1, "C": 4, "D": 2, "E": 1}, [3, 1, 4, 2], None,
])
def test_ratings_must_be_four_integers_from_1_to_5(client, app, ratings):
    headers, session = start(client)
    assert rate(client, headers, session["scenarios"][0], ratings).status_code == 400
    with app.app_context():
        assert Scenario.query.filter(Scenario.completed_at.isnot(None)).count() == 0


def test_nobody_rates_someone_elses_scenario(client):
    _, a = start(client, "ana@example.com")
    b_headers, _ = start(client, "bia@example.com")
    assert rate(client, b_headers, a["scenarios"][0]).status_code == 404


def test_an_abandoned_scenario_goes_to_the_next_participant(client, app):
    a_headers, a = start(client, "ana@example.com")
    for s in a["scenarios"]:
        expire(app, s)
    _, b = start(client, "bia@example.com")
    assert [order_of(app, s) for s in b["scenarios"]] == [0, 1]
    # the old holder can no longer send ratings for them
    res = rate(client, a_headers, a["scenarios"][0])
    assert res.status_code == 409 and res.get_json()["error"] == "reservation_lost"
    with app.app_context():
        assert Scenario.query.filter(Scenario.completed_at.isnot(None)).count() == 0
    # and gets the next free ones when coming back
    again = client.get("/api/session", headers=a_headers).get_json()
    assert [order_of(app, s) for s in again["scenarios"]] == [2, 3]


def test_a_late_holder_keeps_a_scenario_nobody_took(client, app):
    headers, session = start(client)
    one = session["scenarios"][0]
    expire(app, one)
    assert rate(client, headers, one).status_code == 200


def test_coming_back_renews_the_reservation(client, app):
    headers, session = start(client)
    for s in session["scenarios"]:
        expire(app, s)
    assert client.get("/api/session", headers=headers).get_json() == session
    _, other = start(client, "bia@example.com")
    assert [order_of(app, s) for s in other["scenarios"]] == [2, 3]


def test_the_pool_runs_out(client, app):
    for i in range(3):
        headers, session = start(client, f"p{i}@example.com")
        for s in session["scenarios"]:
            assert rate(client, headers, s).status_code == 200
    headers, session = start(client, "late@example.com")
    assert session == {"status": "study_full", "scenarios": []}


def test_the_last_participant_can_finish_with_one_scenario(client, app, tmp_path):
    for i in range(2):
        headers, session = start(client, f"p{i}@example.com")
        for s in session["scenarios"]:
            rate(client, headers, s)
    a_headers, a = start(client, "ana@example.com")
    assert rate(client, a_headers, a["scenarios"][0]).get_json()["status"] == "in_progress"
    b_headers, b = start(client, "bia@example.com")
    assert b["status"] == "study_full"
    assert rate(client, a_headers, a["scenarios"][1]).get_json()["status"] == "completed"


def test_package_files_are_served_as_they_are(client, app, package, tmp_path):
    eid = package[0]["external_id"]
    res = client.get(f"/api/scenarios/{eid}/A.wav")
    assert res.status_code == 200 and res.mimetype == "audio/wav"
    assert res.data == (tmp_path / "study" / "scenarios" / eid / "A.wav").read_bytes()
    assert "immutable" in res.headers["Cache-Control"]
    part = client.get(f"/api/scenarios/{eid}/A.wav", headers={"Range": "bytes=0-3"})
    assert part.status_code == 206 and part.data == b"RIFF"
    assert client.get(f"/api/scenarios/{eid}/context.png").mimetype == "image/png"
    for path in (f"/api/scenarios/{eid}/E.wav", f"/api/scenarios/{eid}/../study.json",
                 f"/api/scenarios/{uuid.uuid4()}/A.wav", "/api/scenarios/../study.json/A.wav"):
        assert client.get(path).status_code == 404


def test_a_package_that_reorders_the_queue_is_refused(app, tmp_path):
    path = tmp_path / "study" / "scenarios.json"
    scenarios = json.loads(path.read_text())
    scenarios[0], scenarios[1] = scenarios[1], scenarios[0]
    for i, s in enumerate(scenarios):
        s["collection_order_v2"] = i
    path.write_text(json.dumps(scenarios))
    with pytest.raises(RuntimeError):
        create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": app.config["SQLALCHEMY_DATABASE_URI"],
                    "STUDY_DIR": tmp_path / "study", "RATELIMIT_ENABLED": False})


def test_panel_and_export(client, app, package):
    headers, session = start(client)
    rate(client, headers, session["scenarios"][0])
    page = client.get("/admin/")
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert "Combina muito bem" in html and "Descrição 0" in html
    # the only check a six-scenario test package fails is the count of 240
    assert html.count(">ERRO<") == 1
    assert client.get("/admin/?todos=1").status_code == 200
    rows = client.get("/admin/ratings.csv").get_data(as_text=True).strip().splitlines()
    assert len(rows) == 2
    head, row = rows[0].split(","), rows[1].split(",")
    record = dict(zip(head, row))
    assert record["external_id"] == package[0]["external_id"] and record["collection_order_v2"] == "0"
    assert [record[f"rating_{s}"] for s in "ABCD"] == ["3", "1", "4", "2"]
    assert record["region"] == "sudeste" and record["questionnaire_version"] == questionnaire.VERSION
    assert record["participant_id"] == headers["X-Participant-Id"]


def test_panel_only_answers_on_listed_hosts(client):
    assert client.get("/admin/", headers={"Host": "pico8-bh.giow.dev"}).status_code == 404
    assert client.get("/admin/", headers={"X-Forwarded-Host": "evil.example"}).status_code == 404
    assert client.get("/admin/ratings.csv", headers={"Host": "evil.example"}).status_code == 404
