"""Export the ratings as CSV, one row per rated scenario.

Run inside the pod:
    kubectl -n pico8-percept exec deploy/server -- python -m app.export > ratings.csv

The research team joins `external_id` and the slot (A to D) with its own key
to know what each clip was; nothing here says it. The questionnaire columns
hold the option codes of app/questionnaire.py at `questionnaire_version`. The
participant id is the HMAC, never the e-mail.
"""

import csv
import sys

from flask import current_app

from . import questionnaire
from .models import Participant, Reservation

COLUMNS = [
    "participant_id", "presented_order", "external_id", "collection_order_v2",
    "rating_A", "rating_B", "rating_C", "rating_D",
    "time_spent_ms", "listened_A_s", "listened_B_s", "listened_C_s", "listened_D_s",
    "reserved_at", "completed_at",
    *questionnaire.CODES, "questionnaire_version", "ui_locale", "participant_created_at",
]


def write_csv(out):
    """Write every rated scenario to the file-like object `out`."""
    records = current_app.config["SCENARIOS"]
    writer = csv.writer(out)
    writer.writerow(COLUMNS)
    rows = (Reservation.query.join(Participant).filter(Reservation.state == "completed")
            .order_by(Participant.created_at, Participant.id, Reservation.completed_at))
    order = {}
    for r in rows:
        p = r.participant
        order[p.id] = order.get(p.id, 0) + 1
        writer.writerow([
            p.id, order[p.id], r.scenario_id, records[r.scenario_id]["collection_order_v2"],
            r.rating_a, r.rating_b, r.rating_c, r.rating_d,
            r.time_spent_ms, r.listened_a_s, r.listened_b_s, r.listened_c_s, r.listened_d_s,
            r.reserved_at.isoformat(), r.completed_at.isoformat(),
            *(getattr(p, name) for name in questionnaire.CODES),
            p.questionnaire_version, p.ui_locale, p.created_at.isoformat(),
        ])


def main():
    from . import create_app

    app = create_app({"RATELIMIT_ENABLED": False})
    with app.app_context():
        write_csv(sys.stdout)


if __name__ == "__main__":
    main()
