"""Which pairs a participant hears.

Each participant gets PAIRS_PER_SYSTEM pairs per generative system. Every pair
is one generated clip against one human clip, both taken from the clips with
the fewest assignments so far (ties broken at random), so evaluations spread
evenly over the catalog. The order of the pairs and the side (track 1 or 2)
of each clip are random. The anchor pair, the same for everyone, comes last.
"""

import random
import threading

from .db import db
from .models import Response, Song

# One gunicorn worker with threads: this lock is enough to stop two concurrent
# first requests from the same participant (double click, React StrictMode)
# from assigning two sets of pairs.
ASSIGN_LOCK = threading.Lock()

_rng = random.SystemRandom()


def _least_used(query, n):
    songs = query.all()
    _rng.shuffle(songs)
    songs.sort(key=lambda s: s.count)  # stable: the shuffle breaks ties
    return songs[:n]


def assign_pairs(participant, systems, per_system):
    generated = []
    for system in systems:
        pool = Song.query.filter_by(system=system, kind="genai", role="pool", active=True)
        generated += [(system, song) for song in _least_used(pool, per_system)]

    humans = _least_used(Song.query.filter_by(kind="human", role="pool", active=True), len(generated))
    generated = generated[: len(humans)]
    _rng.shuffle(generated)

    pairs = []
    for (system, gen), human in zip(generated, humans):
        pair = [gen, human]
        _rng.shuffle(pair)
        pairs.append((system, pair))

    anchor = Song.query.filter_by(role="anchor", active=True).order_by(Song.kind.desc()).all()
    if len(anchor) == 2:
        # Fixed order (human first) so every participant hears the anchor the same way.
        pairs.append(("anchor", anchor))

    responses = []
    for position, (pair_kind, (a, b)) in enumerate(pairs):
        a.count += 1
        b.count += 1
        response = Response(
            participant_id=participant.id,
            position=position,
            track_a_id=a.id,
            track_b_id=b.id,
            pair_kind=pair_kind,
        )
        db.session.add(response)
        responses.append(response)
    db.session.commit()
    return responses
