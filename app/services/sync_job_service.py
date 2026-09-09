from datetime import datetime, timezone, timedelta
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

    @staticmethod
    def claim_next_job(lease_seconds=30):
        now = datetime.now(timezone.utc)

        stmt = (
            db.select(SyncJob)
            .where(
                db.or_(
                    db.and_(
                        (SyncJob.status == "pending") | (SyncJob.status == "retry_pending"),
                        SyncJob.next_attempt_at <= now,
                    ),
                    db.and_(
                        SyncJob.status == "processing",
                        SyncJob.lease_expires_at <= now,
                    ),
                )
            )
            .order_by(SyncJob.next_attempt_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )

        job = db.session.execute(stmt).scalar_one_or_none()

        if job is None:
            db.session.rollback()
            return None

        job.status = "processing"
        job.lease_expires_at = now + timedelta(seconds=lease_seconds)

        db.session.commit()

        return job

    @staticmethod
    def mark_succeeded(job):
        job.status = "succeeded"
        job.lease_expires_at = None
        job.last_error = None
        job.next_attempt_at = None

        db.session.commit()

        return job

    @staticmethod
    def schedule_retry_or_fail(
            job,
            error,
            max_attempts=3,
            base_delay_seconds=2,
    ):
        now = datetime.now(timezone.utc)

        job.attempt_count += 1
        job.last_error = str(error)
        job.lease_expires_at = None

        if job.attempt_count >= max_attempts:
            job.status = "dead_letter"
            job.next_attempt_at = None
        else:
            job.status = "retry_pending"
            backoff_delay = base_delay_seconds * (2 ** (job.attempt_count - 1))
            job.next_attempt_at = now + timedelta(seconds=backoff_delay)

        db.session.commit()
        return job
