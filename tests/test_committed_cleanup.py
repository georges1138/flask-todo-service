from datetime import datetime, timezone
from models import db, SyncJob
from services.sync_job_service import SyncJobService


def test_committed_cleanup_keeps_tables(committed_data_context):
    completed_at = datetime.now(timezone.utc)

    job = SyncJobService.create_completion_email_job(
        email_address="charlie@example.com",
        source_todo_id=789,
        todo_title="Buy golf balls",
        completed_at=completed_at,
    )

    job_idempotency_key = job.idempotency_key

    db.session.commit()

    stmt = (
        db.select(SyncJob.idempotency_key).where(
            SyncJob.idempotency_key == job_idempotency_key,
        )
    )

    with db.engine.connect() as other_connection:
        job_found = other_connection.execute(
            stmt
        ).scalar_one_or_none()

        assert job_found is not None

    committed_data_context()

    with db.engine.connect() as other_connection:
        job_not_found = other_connection.execute(
            stmt
        ).scalar_one_or_none()

        assert job_not_found is None
