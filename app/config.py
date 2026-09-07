import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")

    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")

    EMAIL_SERVICE_URL = os.environ.get("EMAIL_SERVICE_URL")

    SYNC_JOB_POLL_INTERVAL_SECONDS = int(
        os.environ.get("SYNC_JOB_POLL_INTERVAL_SECONDS", "1")
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False
