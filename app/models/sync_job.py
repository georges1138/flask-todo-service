from datetime import datetime, timezone
from models import db


class SyncJob(db.Model):
    __tablename__ = 'sync_jobs'

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    idempotency_key = db.Column(
        db.String(64),
        nullable=False,
        unique=True,
    )

    job_type = db.Column(
        db.String(32),
        nullable=False,
    )

    email_address = db.Column(
        db.String(150),
        nullable=False,
    )

    source_todo_id = db.Column(
        db.Integer,
        nullable=False,
    )

    todo_title = db.Column(
        db.String(108),
        nullable=False,
    )

    completed_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
    )

    status = db.Column(
        db.String(32),
        nullable=False,
        default='pending',
    )

    attempt_count = db.Column(
        db.Integer,
        nullable=False,
        default=0,
    )

    next_attempt_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
    )

    lease_expires_at = db.Column(
        db.DateTime(timezone=True),
        nullable=True,
    )

    last_error = db.Column(
        db.Text,
        nullable=True,
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
