from datetime import datetime, timezone, timedelta
from uuid import UUID

from models import db, SyncJob
from services.sync_job_service import SyncJobService
from sqlalchemy.orm import sessionmaker


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


def test_claim_next_job_claims_eligible_pending_job(app):
    now = datetime.now(timezone.utc)

    job = SyncJob(
        idempotency_key="claim-test-1",
        job_type="email_notification",
        email_address="alice@example.com",
        source_todo_id=1,
        todo_title="Buy milk",
        completed_at=now,
        status="pending",
        attempt_count=0,
        next_attempt_at=now - timedelta(seconds=1),
    )

    db.session.add(job)
    db.session.commit()

    claimed = SyncJobService.claim_next_job(
        lease_seconds=30
    )

    assert claimed is not None
    assert job.id == claimed.id
    assert claimed.status == "processing"
    assert claimed.lease_expires_at is not None
    assert claimed.lease_expires_at > now


def test_claim_next_job_returns_none_when_no_job_is_eligible(app):
    result = SyncJobService.claim_next_job()

    assert result is None


def test_claim_next_job_skips_future_pending_job(app):
    now = datetime.now(timezone.utc)

    job = SyncJob(
        idempotency_key="claim-test-future",
        job_type="email_notification",
        email_address="alice@example.com",
        source_todo_id=2,
        todo_title="Future job",
        completed_at=now,
        status="pending",
        attempt_count=0,
        next_attempt_at=now + timedelta(minutes=5),
    )

    db.session.add(job)
    db.session.commit()

    result = SyncJobService.claim_next_job()

    assert result is None

    db.session.expire_all()
    stored_job = db.session.get(SyncJob, job.id)

    assert stored_job.status == "pending"
    assert stored_job.lease_expires_at is None


def test_claim_next_job_claims_ready_retry_pending_job(app):
    now = datetime.now(timezone.utc)

    job = SyncJob(
        idempotency_key="retry-claim-test",
        job_type="email_notification",
        email_address="alice@example.com",
        source_todo_id=3,
        todo_title="Retry me",
        completed_at=now,
        status="retry_pending",
        attempt_count=1,
        next_attempt_at=now - timedelta(seconds=1),
    )

    db.session.add(job)
    db.session.commit()

    claimed = SyncJobService.claim_next_job(
        lease_seconds=30
    )

    assert claimed is not None
    assert claimed.id == job.id
    assert claimed.status == "processing"
    assert claimed.lease_expires_at is not None


def test_claim_next_job_skips_future_retry_pending_job(app):
    now = datetime.now(timezone.utc)

    job = SyncJob(
        idempotency_key="retry-future-test",
        job_type="email_notification",
        email_address="alice@example.com",
        source_todo_id=4,
        todo_title="Retry later",
        completed_at=now,
        status="retry_pending",
        attempt_count=1,
        next_attempt_at=now + timedelta(minutes=5),
    )

    db.session.add(job)
    db.session.commit()

    result = SyncJobService.claim_next_job()

    assert result is None

    db.session.expire_all()
    stored_job = db.session.get(SyncJob, job.id)

    assert stored_job.status == "retry_pending"
    assert stored_job.lease_expires_at is None


def test_claim_next_job_reclaims_expired_processing_job(app):
    now = datetime.now(timezone.utc)

    job = SyncJob(
        idempotency_key="expired-lease-test",
        job_type="email_notification",
        email_address="alice@example.com",
        source_todo_id=5,
        todo_title="Recover me",
        completed_at=now,
        status="processing",
        attempt_count=1,
        next_attempt_at=now - timedelta(minutes=10),
        lease_expires_at=now - timedelta(seconds=30),
    )

    db.session.add(job)
    db.session.commit()

    old_lease = job.lease_expires_at

    claimed = SyncJobService.claim_next_job(
        lease_seconds=30
    )

    assert claimed is not None
    assert claimed.id == job.id
    assert claimed.status == "processing"
    assert claimed.lease_expires_at > old_lease
    assert claimed.idempotency_key == job.idempotency_key


def test_claim_next_job_skips_processing_job_with_active_lease(app):
    now = datetime.now(timezone.utc)

    job = SyncJob(
        idempotency_key="active-lease-test",
        job_type="email_notification",
        email_address="alice@example.com",
        source_todo_id=6,
        todo_title="Still owned",
        completed_at=now,
        status="processing",
        attempt_count=1,
        next_attempt_at=now - timedelta(minutes=10),
        lease_expires_at=now + timedelta(minutes=5),
    )

    db.session.add(job)
    db.session.commit()

    old_lease = job.lease_expires_at

    result = SyncJobService.claim_next_job()

    assert result is None

    db.session.expire_all()
    reloaded_job = db.session.get(SyncJob, job.id)

    assert reloaded_job.status == "processing"
    assert reloaded_job.lease_expires_at == old_lease


def test_skip_locked_returns_none_when_only_job_is_locked(app):
    now = datetime.now(timezone.utc)

    job = SyncJob(
        idempotency_key="skip-locked-only-job",
        job_type="email_notification",
        email_address="alice@example.com",
        source_todo_id=7,
        todo_title="Locked job",
        completed_at=now,
        status="pending",
        attempt_count=0,
        next_attempt_at=now - timedelta(seconds=1),
    )

    db.session.add(job)
    db.session.commit()

    SessionFactory = sessionmaker(bind=db.engine)

    session_a = SessionFactory()
    session_b = SessionFactory()

    try:
        stmt = (
            db.select(
                SyncJob
            )
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

        job_a = session_a.execute(stmt).scalar_one_or_none()
        job_b = session_b.execute(stmt).scalar_one_or_none()

        assert job_a is not None
        assert job_b is None

    finally:
        session_a.rollback()
        session_b.rollback()
        session_a.close()
        session_b.close()


def test_skip_locked_claims_next_available_job(app):
    now = datetime.now(timezone.utc)

    first_job = SyncJob(
        idempotency_key="skip-locked-first",
        job_type="email_notification",
        email_address="alice@example.com",
        source_todo_id=8,
        todo_title="First job",
        completed_at=now,
        status="pending",
        attempt_count=0,
        next_attempt_at=now - timedelta(seconds=2),
    )

    second_job = SyncJob(
        idempotency_key="skip-locked-second",
        job_type="email_notification",
        email_address="bob@example.com",
        source_todo_id=9,
        todo_title="Second job",
        completed_at=now,
        status="pending",
        attempt_count=0,
        next_attempt_at=now - timedelta(seconds=1),
    )

    db.session.add_all([first_job, second_job])
    db.session.commit()

    SessionFactory = sessionmaker(bind=db.engine)

    session_a = SessionFactory()
    session_b = SessionFactory()

    try:
        stmt = (
            db.select(
                SyncJob
            )
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

        job_a = session_a.execute(stmt).scalar_one_or_none()
        job_b = session_b.execute(stmt).scalar_one_or_none()

        assert job_a is not None
        assert job_b is not None
        assert job_a.id != job_b.id

    finally:
        session_a.rollback()
        session_b.rollback()
        session_a.close()
        session_b.close()


def test_mark_succeeded_clears_processing_state(app):
    now = datetime.now(timezone.utc)

    job = SyncJob(
        idempotency_key="mark-success-test",
        job_type="email_notification",
        email_address="alice@example.com",
        source_todo_id=10,
        todo_title="Successful job",
        completed_at=now,
        status="processing",
        attempt_count=1,
        next_attempt_at=now,
        lease_expires_at=now + timedelta(seconds=30),
        last_error="previous failure",
    )

    db.session.add(job)
    db.session.commit()

    result = SyncJobService.mark_succeeded(job)

    assert result.id == job.id
    assert result.status == "succeeded"
    assert result.lease_expires_at is None
    assert result.last_error is None
    assert result.next_attempt_at is None
    assert result.attempt_count == 1

    db.session.expire_all()
    reloaded_job = db.session.get(SyncJob, job.id)
    assert result.status == reloaded_job.status
    assert reloaded_job.status == "succeeded"
    assert reloaded_job.lease_expires_at is None
    assert reloaded_job.last_error is None
    assert reloaded_job.next_attempt_at is None
    assert reloaded_job.attempt_count == 1


def test_schedule_retry_or_fail_first_failure_schedules_retry(app):
    before = datetime.now(timezone.utc)

    job = SyncJob(
        idempotency_key="retry-first-failure",
        job_type="email_notification",
        email_address="alice@example.com",
        source_todo_id=11,
        todo_title="Retry after failure",
        completed_at=before,
        status="processing",
        attempt_count=0,
        next_attempt_at=before,
        lease_expires_at=before + timedelta(seconds=30),
    )

    db.session.add(job)
    db.session.commit()

    result = SyncJobService.schedule_retry_or_fail(
        job,
        error=TimeoutError("email timeout"),
        max_attempts=3,
        base_delay_seconds=2,
    )

    after = datetime.now(timezone.utc)

    assert result.attempt_count == 1
    assert result.status == "retry_pending"
    assert result.last_error == "email timeout"
    assert result.lease_expires_at is None
    assert result.next_attempt_at is not None

    assert (
        before + timedelta(seconds=2)
        <= result.next_attempt_at
        <= after + timedelta(seconds=2)
    )


def test_schedule_retry_or_fail_second_failure_uses_exponential_backoff(app):
    before = datetime.now(timezone.utc)

    job = SyncJob(
        idempotency_key="retry-second-failure",
        job_type="email_notification",
        email_address="alice@example.com",
        source_todo_id=12,
        todo_title="Retry with longer delay",
        completed_at=before,
        status="processing",
        attempt_count=1,
        next_attempt_at=before,
        lease_expires_at=before + timedelta(seconds=30),
    )

    db.session.add(job)
    db.session.commit()

    result = SyncJobService.schedule_retry_or_fail(
        job,
        error="email service unavailable",
        max_attempts=3,
        base_delay_seconds=2,
    )

    after = datetime.now(timezone.utc)

    assert result.attempt_count == 2
    assert result.status == "retry_pending"
    assert result.last_error == "email service unavailable"
    assert result.lease_expires_at is None
    assert result.next_attempt_at is not None

    assert (
        before + timedelta(seconds=4)
        <= result.next_attempt_at
        <= after + timedelta(seconds=4)
    )


def test_schedule_retry_or_fail_third_failure_marks_failed(app):
    now = datetime.now(timezone.utc)

    job = SyncJob(
        idempotency_key="retry-third-failure",
        job_type="email_notification",
        email_address="alice@example.com",
        source_todo_id=13,
        todo_title="Three strikes",
        completed_at=now,
        status="processing",
        attempt_count=2,
        next_attempt_at=now,
        lease_expires_at=now + timedelta(seconds=30),
    )

    db.session.add(job)
    db.session.commit()

    result = SyncJobService.schedule_retry_or_fail(
        job,
        error="email service still unavailable",
        max_attempts=3,
        base_delay_seconds=2,
    )

    assert result.attempt_count == 3
    assert result.status == "failed"
    assert result.last_error == "email service still unavailable"
    assert result.lease_expires_at is None
    assert result.next_attempt_at is None

    db.session.expire_all()
    reloaded_job = db.session.get(SyncJob, job.id)
    assert result.status == reloaded_job.status
    assert reloaded_job.status == "failed"
    assert reloaded_job.lease_expires_at is None
    assert reloaded_job.last_error == "email service still unavailable"
    assert reloaded_job.next_attempt_at is None
