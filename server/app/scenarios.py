"""The research package and the queue that hands its scenarios out.

The package (STUDY_DIR) is the `public/` folder prepared by the research team:
study.json, scenarios.json and scenarios/<external_id>/{context.png,A..D.wav}.
Its files are served as they are. Which clip of a scenario comes from which
source is not in the package and is never known to this app.

Queue rules, from the package's handoff notes:

* scenarios go out in `collection_order_v2`, the next free ones first;
* a scenario held by one participant is not given to another;
* a holder who goes quiet for RESERVATION_MINUTES can lose the scenario to the
  next participant, and can no longer send ratings for it after that;
* a rated scenario leaves the pool for good.
"""

import json
import re
import threading
from datetime import timedelta

from .db import db
from .models import Reservation, Scenario, utcnow

SLOTS = ("A", "B", "C", "D")
ID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")

# One gunicorn worker with threads: this lock makes "find the next free
# scenarios and take them" a single step.
QUEUE_LOCK = threading.Lock()


def load_package(study_dir):
    study = json.loads((study_dir / "study.json").read_text())
    scenarios = json.loads((study_dir / "scenarios.json").read_text())
    if [s["value"] for s in study["scale"]] != [1, 2, 3, 4, 5]:
        raise RuntimeError("study.json: the scale must be the values 1 to 5")
    seen = set()
    for index, s in enumerate(scenarios):
        eid = s["external_id"]
        if not ID_RE.match(eid) or eid in seen:
            raise RuntimeError(f"scenarios.json: bad or repeated external_id {eid!r}")
        seen.add(eid)
        if s["collection_order_v2"] != index:
            raise RuntimeError(f"scenarios.json: record {index} has collection_order_v2 {s['collection_order_v2']}")
        if s["context_image"] != f"scenarios/{eid}/context.png" or any(
            s["audios"].get(slot) != f"scenarios/{eid}/{slot}.wav" for slot in SLOTS
        ):
            raise RuntimeError(f"scenarios.json: unexpected file paths in {eid}")
    return study, scenarios


def sync_scenarios(scenarios):
    """Insert the package's scenarios; refuse a package that disagrees with the database."""
    known = {s.external_id: s for s in Scenario.query.all()}
    for record in scenarios:
        row = known.pop(record["external_id"], None)
        if row is None:
            db.session.add(Scenario(external_id=record["external_id"], position=record["collection_order_v2"]))
        elif row.position != record["collection_order_v2"]:
            raise RuntimeError(f"scenario {row.external_id} changed position; the queue order must not change")
    if known:
        raise RuntimeError(f"{len(known)} scenarios in the database are not in the package")
    db.session.commit()


def ensure_reservations(participant, target, minutes):
    """The participant's scenarios, in the order they were handed out.

    Renews what they still hold, drops what was given to someone else, and
    takes the next free scenarios until they have `target` (or the pool ends).
    Call with QUEUE_LOCK held.
    """
    now = utcnow()
    expires = now + timedelta(minutes=minutes)
    kept = []
    for r in participant.reservations:
        if r.state == "active":
            if r.scenario.holder_id == r.id:
                r.expires_at = expires
            else:
                r.state = "lost"
        if r.state != "lost":
            kept.append(r)

    need = target - len(kept)
    if need > 0 and participant.finished_at is None:
        free = (
            db.session.query(Scenario, Reservation)
            .outerjoin(Reservation, Scenario.holder_id == Reservation.id)
            .filter(Scenario.completed_at.is_(None))
            .filter(db.or_(Scenario.holder_id.is_(None), Reservation.expires_at <= now))
            .order_by(Scenario.position)
            .limit(need)
            .all()
        )
        for scenario, previous in free:
            if previous is not None:
                previous.state = "lost"
            reservation = Reservation(participant_id=participant.id, scenario_id=scenario.external_id, expires_at=expires)
            db.session.add(reservation)
            db.session.flush()
            scenario.holder_id = reservation.id
            kept.append(reservation)

    if kept and participant.finished_at is None and all(r.state == "completed" for r in kept):
        participant.finished_at = now
    db.session.commit()
    return kept


def complete(reservation, ratings, extra):
    """Store the four ratings. Returns "ok", "repeat" (already stored) or "lost".

    Call with QUEUE_LOCK held.
    """
    if reservation.state == "completed":
        return "repeat"
    scenario = reservation.scenario
    if reservation.state == "lost" or scenario.holder_id != reservation.id or scenario.completed_at is not None:
        reservation.state = "lost"
        db.session.commit()
        return "lost"
    now = utcnow()
    reservation.rating_a, reservation.rating_b, reservation.rating_c, reservation.rating_d = (ratings[s] for s in SLOTS)
    for name, value in extra.items():
        setattr(reservation, name, value)
    reservation.state = "completed"
    reservation.completed_at = now
    scenario.completed_at = now
    db.session.commit()
    return "ok"
