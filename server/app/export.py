"""Export answers as CSV, one row per answered pair.

Run inside the pod:
    kubectl -n pico8-percept exec deploy/server -- python -m app.export > answers.csv

Columns name each track by system and kind, so the analysis needs nothing else
from the catalog. The participant id is the HMAC, never the e-mail.
"""

import csv
import sys

from .models import Participant, Response

COLUMNS = [
    "participant_id", "position", "question", "pair_id", "pair_role", "tag", "game_tid",
    "track_a_id", "track_a_system", "track_a_kind", "track_a_source",
    "track_b_id", "track_b_system", "track_b_kind", "track_b_source",
    "choice", "chose_human", "familiarity", "comments",
    "time_spent_ms", "listened_a_s", "listened_b_s", "assigned_at", "answered_at",
    "age", "language", "formal_experience", "practical_experience", "knows_ai_music",
    "chiptune_familiarity", "ui_locale", "participant_created_at", "profile_completed_at",
]


def write_csv(out):
    """Write every answered pair to the file-like object `out`."""
    writer = csv.writer(out)
    writer.writerow(COLUMNS)
    rows = (Response.query.join(Participant).filter(Response.answered_at.isnot(None))
            .order_by(Participant.created_at, Response.position))
    for r in rows:
        p = r.participant
        writer.writerow([
            p.id, r.position, r.question, r.pair_id, r.pair.role, r.pair.tag, r.pair.game_tid,
            r.track_a.id, r.track_a.system, r.track_a.kind, r.track_a.source_id,
            r.track_b.id, r.track_b.system, r.track_b.kind, r.track_b.source_id,
            r.choice, int(r.chose_human), r.familiarity, r.comments or "",
            r.time_spent_ms, r.listened_a_s, r.listened_b_s,
            r.assigned_at.isoformat(), r.answered_at.isoformat(),
            p.age, p.language, p.formal_experience, p.practical_experience, p.knows_ai_music,
            p.chiptune_familiarity, p.ui_locale, p.created_at.isoformat(),
            p.profile_completed_at.isoformat() if p.profile_completed_at else "",
        ])


def main():
    from . import create_app

    app = create_app({"RATELIMIT_ENABLED": False})
    with app.app_context():
        write_csv(sys.stdout)


if __name__ == "__main__":
    main()
