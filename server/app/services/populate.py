import logging
import uuid
import json
import os
from flask import current_app

from app.models import Song, ExperimentType, Pair
from app.repository import db
from app.services.s3 import get_s3_client


def get_audio_labels():
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    labels_path = os.path.join(project_root, 'resources', 'labels.json')
    try:
        with open(labels_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Error reading labels file: {e}")
        return {}

def populate_rq1_experiment(s3_client, bucket_name, base_path, audio_labels):
    rq1_prefix = f"{base_path}rq1/"
    response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=rq1_prefix)

    if 'Contents' in response:
        folder_pairs = {}
        for obj in response['Contents']:
            file_key = obj['Key']
            if file_key.endswith('/'):  # Skip folders
                continue
            folder_name = file_key.split('/')[-2]
            full_path = file_key
            song_key = file_key.split('/')[-1].split('.')[0]
            song_type = "genai" if get_audio_labels().get(song_key) == "genai" else "human"

            # Add song to folder_pairs dictionary
            if folder_name not in folder_pairs:
                folder_pairs[folder_name] = []
            folder_pairs[folder_name].append((full_path, song_type))

        # Add pairs to the database
        for folder_name, songs in folder_pairs.items():
            if len(songs) == 2:  # Ensure there are exactly two songs in the folder
                songA_path, songA_type = songs[0]
                songB_path, songB_type = songs[1]

                # Add songs if they don't exist
                songA = Song.query.filter_by(name=songA_path).first()
                if not songA:
                    songA = Song(id=str(uuid.uuid4()), name=songA_path, experiment=ExperimentType.rq1, count=0, type=songA_type)
                    db.session.add(songA)

                songB = Song.query.filter_by(name=songB_path).first()
                if not songB:
                    songB = Song(id=str(uuid.uuid4()), name=songB_path, experiment=ExperimentType.rq1, count=0, type=songB_type)
                    db.session.add(songB)

                # Add pair
                existing_pair = Pair.query.filter_by(trackA=songA, trackB=songB, experiment=ExperimentType.rq1).first()
                if not existing_pair:
                    pair = Pair(id=str(uuid.uuid4()), trackA=songA, trackB=songB, experiment=ExperimentType.rq1, count=0)
                    db.session.add(pair)


def populate_random_experiment(s3_client, bucket_name, base_path, audio_labels):
    random_prefix = f"{base_path}random/"
    response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=random_prefix)
    if 'Contents' in response:
        for obj in response['Contents']:
            file_key = obj['Key']
            if file_key.endswith('/'):
                continue
            song_key = file_key.split('/')[-1].split('.')[0]
            song_type = "genai" if get_audio_labels().get(song_key) == "genai" else "human"

            song_name = file_key  # Use the full path as the song name
            existing_song = Song.query.filter_by(name=song_name).first()
            if not existing_song:
                new_song = Song(id=str(uuid.uuid4()), name=song_name, experiment=ExperimentType.random, count=0, type=song_type)
                db.session.add(new_song)

def populate_default_pair(s3_client, bucket_name, base_path, audio_labels):
    # Create default pair if it doesn't exist
    default_pair_prefix = f"{base_path}default-pair/"
    response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=default_pair_prefix)

    songs = []
    for obj in response.get('Contents', []):
        file_key = obj['Key']
        if file_key.endswith('/'):
            continue
        song_key = file_key.split('/')[-1].split('.')[0]
        song_type = "genai" if get_audio_labels().get(song_key) == "genai" else "human"

        # Add song to the database if it doesn't exist
        existing_song = Song.query.filter_by(name=file_key).first()
        if not existing_song:
            new_song = Song(
                id=str(uuid.uuid4()),
                name=file_key,
                experiment=ExperimentType.default,
                count=0,
                type=song_type
            )
            db.session.add(new_song)
            songs.append(new_song)
        else:
            songs.append(existing_song)

    # Ensure there are exactly two songs for the default pair
    if len(songs) == 2:
        default_pair = Pair.query.filter_by(experiment=ExperimentType.default).first()
        if not default_pair:
            default_pair = Pair(
                id=str(uuid.uuid4()),
                trackA_id=songs[0].id,
                trackB_id=songs[1].id,
                experiment=ExperimentType.default,
                count=0
            )
            db.session.add(default_pair)

def populate_song_and_pairs():
    # Get S3 configuration
    bucket_name = current_app.config.get('S3_BUCKET')
    base_path = current_app.config.get('SONGS_BASE_PATH_S3')
    if not bucket_name or not base_path:
        raise ValueError("S3 bucket or base path is not configured")

    s3_client = get_s3_client()

    audio_labels = get_audio_labels()
    if len(audio_labels) == 0:
        raise ValueError("Audio labels configuration is missing")

    populate_rq1_experiment(s3_client, bucket_name, base_path, audio_labels)
    populate_random_experiment(s3_client, bucket_name, base_path, audio_labels)
    populate_default_pair(s3_client, bucket_name, base_path, audio_labels)

    db.session.commit()

    logging.info("Populated songs and pairs successfully")

