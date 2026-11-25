import json
import logging
import os

import boto3
from flask import current_app, jsonify

from app.models import ExperimentType, Song, Pair
from app.repository import db

s3_client = None

def get_s3_client():
    global s3_client
    if s3_client is None:
        with current_app.app_context():
            s3_client = boto3.client(
                's3',
                region_name=current_app.config['S3_REGION']
            )
    return s3_client

def get_bucket_name():
    with current_app.app_context():
        return current_app.config.get('S3_BUCKET')

def generate_url(object_key, expiration=3600):
    client = get_s3_client()
    return client.generate_presigned_url(
        'get_object',
        Params={'Bucket': get_bucket_name(), 'Key': object_key},
        ExpiresIn=expiration
    )



