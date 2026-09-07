from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import httpx
import pytest

from models import db
from models.sync_job import SyncJob
from services.sync_job_worker import SyncJobWorker


class FakeEmailClient:
    def __init__(self):
        self.called = False
        self.kwargs = None

    def send_email(self, **kwargs):
        self.called = True
        self.kwargs = kwargs


class FailingEmailClient:
    def send_email(self, **kwargs):
        request = httpx.Request(
            "POST",
            "http://email-service.test/emails",
        )

        raise httpx.ConnectError(
            "email service unavailable",
            request=request,
        )


class BrokenEmailClient:
    def send_email(self, **kwargs):
        raise ValueError("unexpected bug")


def test_run_once_returns_false_when_no_job(app):
    fake_email_client = FakeEmailClient()
    worker = SyncJobWorker(fake_email_client)

    result = worker.run_once()

    assert result is False
    assert fake_email_client.called is False


def test_run_once_marks_job_succeeded_when_email_succeeds(app):
    now = datetime.now(timezone.utc)

    job = SyncJob(
        idempotency_key="worker-success",
        job_type="email_notification",
        email_address="alice@example.com",
        source_todo_id=21,
        todo_title="Finish report",
        completed_at=now,
        status="pending",
        attempt_count=0,
        next_attempt_at=now,
    )

    db.session.add(job)
    db.session.commit()

    fake_email_client = FakeEmailClient()
    worker = SyncJobWorker(fake_email_client)

    result = worker.run_once()

    assert result is True
    assert fake_email_client.called is True

    assert fake_email_client.kwargs["to"] == job.email_address
    assert fake_email_client.kwargs["subject"] == "Todo completed"
    assert fake_email_client.kwargs["body"] == f"You completed: {job.todo_title}"
    assert fake_email_client.kwargs["idempotency_key"] == job.idempotency_key

    db.session.expire_all()
    reloaded_job = db.session.get(SyncJob, job.id)
    assert reloaded_job.status == "succeeded"
    assert reloaded_job.lease_expires_at is None
    assert reloaded_job.next_attempt_at is None


def test_run_once_schedules_retry_when_email_fails(app):
    now = datetime.now(timezone.utc)

    job = SyncJob(
        idempotency_key="worker-email-failure",
        job_type="email_notification",
        email_address="alice@example.com",
        source_todo_id=22,
        todo_title="Retry me",
        completed_at=now,
        status="pending",
        attempt_count=0,
        next_attempt_at=now,
    )

    db.session.add(job)
    db.session.commit()

    worker = SyncJobWorker(FailingEmailClient())

    before = datetime.now(timezone.utc)

    result = worker.run_once()

    after = datetime.now(timezone.utc)

    assert result is True
    db.session.expire_all()
    reloaded_job = db.session.get(SyncJob, job.id)

    assert reloaded_job.attempt_count == 1
    assert reloaded_job.status == "retry_pending"
    assert reloaded_job.last_error == "email service unavailable"
    assert reloaded_job.lease_expires_at is None
    assert reloaded_job.next_attempt_at is not None
    assert (
            before + timedelta(seconds=2)
            <= reloaded_job.next_attempt_at
            <= after + timedelta(seconds=2)
    )


def test_run_once_does_not_retry_unexpected_exception(app):
    now = datetime.now(timezone.utc)

    job = SyncJob(
        idempotency_key="worker-unexpected-error",
        job_type="email_notification",
        email_address="alice@example.com",
        source_todo_id=23,
        todo_title="Unexpected failure",
        completed_at=now,
        status="pending",
        attempt_count=0,
        next_attempt_at=now,
    )

    db.session.add(job)
    db.session.commit()

    worker = SyncJobWorker(BrokenEmailClient())

    with pytest.raises(ValueError, match="unexpected bug"):
        worker.run_once()

    db.session.expire_all()
    reloaded_job = db.session.get(SyncJob, job.id)

    assert reloaded_job.status == "processing"
    assert reloaded_job.attempt_count == 0


def test_run_forever_sleeps_only_when_no_job(app):
    worker = SyncJobWorker(
        FakeEmailClient(),
        poll_interval_seconds=3,
    )

    with patch.object(
        worker,
        "run_once",
        side_effect=[True, False, StopIteration],
    ):
        with patch("services.sync_job_worker.time.sleep") as mock_sleep:
            with pytest.raises(StopIteration):
                worker.run_forever()

    mock_sleep.assert_called_once()
    mock_sleep.assert_called_with(3)
