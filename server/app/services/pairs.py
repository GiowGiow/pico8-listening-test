import logging
import random
import uuid
from itertools import count

from sqlalchemy import asc
from app.models import Pair, ExperimentType, Song
from app.repository import db


def get_default_pair():
    pairs = []
    default_pair = Pair.query.filter(
        Pair.experiment == ExperimentType.default
    ).first()

    if not  default_pair:
        return

    pairs.append([default_pair.trackA.name, default_pair.trackB.name])
    default_pair.count += 1
    default_pair.trackA.count += 1
    default_pair.trackB.count += 1

    return pairs

def get_least_evaluated_pairs(experiment: ExperimentType, num: int):
    pairs = []
    used_track_ids = set()

    # Busca todos os pares do tipo desejado, ordenados pelo count crescente
    candidate_pairs = Pair.query.filter(
        Pair.experiment == experiment
    ).order_by(
        asc(Pair.count)
    ).all()

    for pair in candidate_pairs:
        if len(pairs) >= num:
            break

        # Checa se algum dos track_ids já foi usado
        if (pair.trackA_id in used_track_ids) or (pair.trackB_id in used_track_ids):
            continue

        # Adiciona o par e marca os track_ids como usados
        pairs.append([pair.trackA.name, pair.trackB.name])
        used_track_ids.add(pair.trackA_id)
        used_track_ids.add(pair.trackB_id)

        pair.count += 1
        pair.trackA.count += 1
        pair.trackB.count += 1

    return pairs

def get_random_pairs(experiment: ExperimentType, num: int):
    pairs = []
    used_track_ids = set()

    # Filter songs by type and order them by count
    genai_songs = Song.query.filter(
        Song.experiment == experiment,
        Song.type == "genai"
    ).order_by(
        asc(Song.count)
    ).all()

    human_songs = Song.query.filter(
        Song.experiment == experiment,
        Song.type == "human"
    ).order_by(
        asc(Song.count)
    ).all()

    for i in range(min(len(genai_songs), len(human_songs))):
        if len(pairs) >= num:
            break

        trackA = genai_songs[i]
        trackB = human_songs[i]

        # Check if any of the track_ids have already been used
        if (trackA.id in used_track_ids) or (trackB.id in used_track_ids):
            continue

        # Add the pair and mark the track_ids as used
        pairs.append([trackA.name, trackB.name])
        used_track_ids.add(trackA.id)
        used_track_ids.add(trackB.id)

        trackA.count += 1
        trackB.count += 1

        add_pair_to_table(trackA_id=trackA.id, trackB_id=trackB.id, experiment=experiment)

    return pairs

def add_pair_to_table(trackA_id, trackB_id, experiment):
    try:
        # Check if the pair already exists in the database
        existing_pair = Pair.query.filter_by(
            trackA_id=trackA_id,
            trackB_id=trackB_id,
            experiment=experiment,
        ).first()

        if existing_pair:
            existing_pair.count += 1
        else:
            pair = Pair(
                id=str(uuid.uuid4()),
                trackA=Song.query.get(trackA_id),
                trackB=Song.query.get(trackB_id),
                experiment=experiment,
                count=1
            )
            db.session.add(pair)

    except Exception as e:
        logging.error("Error adding pair to table", exc_info=True)
        raise e
