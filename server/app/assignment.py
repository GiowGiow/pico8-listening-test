"""Which pairs a participant hears.

Each participant gets PAIRS_PER_TAG pairs of every game tag, taken from the
pairs with the fewest assignments so far (ties broken at random), so answers
spread evenly over the catalog and every tag weighs the same. The order of the
pairs and the side (track 1 or 2) of each clip are random. The anchor pair,
the same for everyone, comes last.
"""

import random
import threading

from .db import db
from .models import Pair, Response

# One gunicorn worker with threads: this lock is enough to stop two concurrent
# first requests from the same participant (double click, React StrictMode)
# from assigning two sets of pairs.
ASSIGN_LOCK = threading.Lock()

_rng = random.SystemRandom()


def _least_used(pairs, n):
    pairs = list(pairs)
    _rng.shuffle(pairs)
    pairs.sort(key=lambda p: p.count)  # stable: the shuffle breaks ties
    return pairs[:n]


def assign_pairs(participant, tags, per_tag, question):
    chosen = []
    for tag in tags:
        pool = Pair.query.filter_by(tag=tag, role="pool", active=True).all()
        chosen += _least_used(pool, per_tag)
    _rng.shuffle(chosen)

    sided = []
    for pair in chosen:
        tracks = [pair.human_id, pair.genai_id]
        _rng.shuffle(tracks)
        sided.append((pair, tracks))
    for anchor in Pair.query.filter_by(role="anchor", active=True).order_by(Pair.id).all():
        # Fixed side (original first) so every participant hears the anchor the same way.
        sided.append((anchor, [anchor.human_id, anchor.genai_id]))

    responses = []
    for position, (pair, (a, b)) in enumerate(sided):
        pair.count += 1
        response = Response(
            participant_id=participant.id, position=position, pair_id=pair.id,
            track_a_id=a, track_b_id=b, question=question,
        )
        db.session.add(response)
        responses.append(response)
    db.session.commit()
    return responses
