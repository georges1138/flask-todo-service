from datetime import datetime, timezone
from models import db, SyncJob
from services.sync_job_service import SyncJobService


def test_committed_job_visible_to_independent_connection(committed_data_context):
    completed_at = datetime.now(timezone.utc)

    job = SyncJobService.create_completion_email_job(
        email_address="charlie@example.com",
        source_todo_id=789,
        todo_title="Buy golf balls",
        completed_at=completed_at,
    )

    job_idempotency_key = job.idempotency_key

    db.session.commit()

    # 4. Build a SELECT statement that looks up that key.
    stmt = (
        db.select(SyncJob.idempotency_key).where(
            SyncJob.idempotency_key == job_idempotency_key,
        )
    )

    with db.engine.connect() as other_connection:
        job_found_idempotency_key = other_connection.execute(
            stmt
        ).scalar_one_or_none()

    # 6. Assert that the independent connection found the job.
    assert job_found_idempotency_key == job_idempotency_key
