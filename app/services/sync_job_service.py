from datetime import datetime, timezone
from uuid import uuid4

from models import db, SyncJob


class SyncJobService:

    @staticmethod
    def create_completion_email_job(
        email_address,
        source_todo_id,
        todo_title,
        completed_at,
    ):
        new_sync_job = SyncJob(
            idempotency_key=str(uuid4()),
            job_type='email_notification',
            email_address=email_address,
            source_todo_id=source_todo_id,
            todo_title=todo_title,
            completed_at=completed_at,
            next_attempt_at=datetime.now(timezone.utc)
        )

        db.session.add(new_sync_job)
        return new_sync_job
