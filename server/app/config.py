import os

basedir = os.path.abspath(os.path.dirname(__file__))

project_root = os.path.dirname(basedir)

class Config:
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    S3_BUCKET = os.getenv('S3_BUCKET', 'pairs-files')
    S3_KEY = os.getenv('S3_KEY', 'tracks.json')
    S3_REGION = os.getenv('S3_REGION', 'us-east-1')

class DevelopmentConfig(Config):
    # DEBUG = True

    db_directory = os.path.join(project_root, 'database')
    os.makedirs(db_directory, exist_ok=True)
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(project_root, 'database', 'local_dev.db')

class ProductionConfig(Config):
    SQLALCHEMY_DATABASE_URI = 'postgresql+psycopg2://postgres:adcruim123!@survey-database-hml.cqze80s4i0mc.us-east-1.rds.amazonaws.com/survey_responses_hml'