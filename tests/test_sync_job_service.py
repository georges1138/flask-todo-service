from datetime import datetime, timezone
from uuid import UUID

from models import db, SyncJob
from services.sync_job_service import SyncJobService


def test_create_completion_email_job(app):
    completed_at = datetime.now(timezone.utc)

    job = SyncJobService.create_completion_email_job(
        email_address="alice@example.com",
        source_todo_id=123,
        todo_title="Buy milk",
        completed_at=completed_at,
    )

    db.session.commit()

    assert job.email_address == "alice@example.com"
    assert job.source_todo_id == 123
    assert job.todo_title == "Buy milk"
    assert job.completed_at == completed_at

    assert job.job_type == "email_notification"

    assert job.status == "pending"
    assert job.attempt_count == 0

    assert UUID(job.idempotency_key)

    assert job.next_attempt_at is not None
    assert abs((job.next_attempt_at - completed_at).total_seconds()) < 5

    assert job.lease_expires_at is None
    assert job.last_error is None

    assert job.created_at is not None

    # Prove the row actually reached the database rather than just the
    # session's identity map. Capture what we need before detaching.
    job_id = job.id
    idempotency_key = job.idempotency_key
    db.session.expunge_all()

    persisted = db.session.get(SyncJob, job_id)
    assert persisted is not None
    assert persisted is not job
    assert persisted.idempotency_key == idempotency_key
    assert persisted.email_address == "alice@example.com"
    assert persisted.source_todo_id == 123
    assert persisted.todo_title == "Buy milk"
    assert persisted.job_type == "email_notification"
    assert persisted.status == "pending"
    assert persisted.attempt_count == 0


def test_create_completion_email_job_does_not_commit(app):
    """The service stages the job; the caller owns the transaction."""
    SyncJobService.create_completion_email_job(
        email_address="bob@example.com",
        source_todo_id=456,
        todo_title="Walk dog",
        completed_at=datetime.now(timezone.utc),
    )

    db.session.rollback()

    assert db.session.query(SyncJob).count() == 0
