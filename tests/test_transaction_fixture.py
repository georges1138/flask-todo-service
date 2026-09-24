from datetime import datetime, timezone
import pytest

from models import db, Todo, User, SyncJob
from services.sync_job_service import SyncJobService


def test_db_session_uses_test_connection(test_transaction):

    # Existing assertion:
    assert db.session.connection() is test_transaction

    assert db.session.get_bind(mapper=Todo) is test_transaction


def test_transaction_boundary(test_transaction):

    assert test_transaction.in_transaction() == True

    db.session.commit()

    assert test_transaction.in_transaction() == True


def test_session_rollback_preserves_outer_transaction(test_transaction):

    assert test_transaction.in_transaction() == True

    db.session.execute(db.text("SELECT 1"))

    db.session.rollback()

    assert test_transaction.in_transaction() == True


def test_session_commit_preserves_outer_transaction_with_data(test_transaction):
    username = "test_user23"
    email = "test_user23@email.invalid"

    new_user = User(username=username, email=email)
    new_user.set_password('apple_123')

    db.session.add(new_user)
    db.session.commit()

    assert test_transaction.in_transaction() == True

    db.session.expire_all()

    stmt = db.select(User).where(
        User.username == username
    )

    selected_user = db.session.execute(
        stmt
    ).scalar_one_or_none()

    assert selected_user is not None


@pytest.mark.parametrize(
    'attempt',
    [1, 2],
)
def test_transaction_rollback_prevents_data_leakage(test_transaction, attempt):
    username = "test_user_dne"
    email = "test_user_dne@email.invalid"

    stmt = (
        db.select(User).where(
            User.username == username,
        )
    )

    user_not_found = db.session.execute(
        stmt
    ).scalar_one_or_none()

    assert user_not_found is None

    new_user = User(username=username, email=email)
    new_user.set_password('apple_123')

    db.session.add(new_user)
    db.session.commit()

    user_found = db.session.execute(
        stmt
    ).scalar_one_or_none()

    assert user_found is not None


def test_session_rollback_does_not_undo_prior_session_commit(test_transaction):
    username = "test_user_commit"
    email = "test_user_commit@email.invalid"

    new_user = User(username=username, email=email)
    new_user.set_password('orange_456')

    db.session.add(new_user)
    db.session.commit()

    db.session.rollback()

    stmt = (
        db.select(User).where(
            User.username == username,
        )
    )

    user_found = db.session.execute(
        stmt
    ).scalar_one_or_none()

    assert user_found is not None


def test_completion_email_job_remains_uncommitted(test_transaction):
    job = SyncJobService.create_completion_email_job(
        email_address="junior@example.com",
        source_todo_id=678,
        todo_title="Walk dog",
        completed_at=datetime.now(timezone.utc),
    )

    job_idempotency_key = job.idempotency_key
    db.session.rollback()

    stmt = (
        db.select(SyncJob).where(
            SyncJob.idempotency_key == job_idempotency_key,
        )
    )
    lookup_job = db.session.execute(
        stmt
    ).scalar_one_or_none()

    assert lookup_job is None


def test_unexpected_commit_makes_completion_job_survive_rollback(test_transaction):
    job = SyncJobService.create_completion_email_job(
        email_address="junior@example.com",
        source_todo_id=678,
        todo_title="Walk dog",
        completed_at=datetime.now(timezone.utc),
    )

    job_idempotency_key = job.idempotency_key
    db.session.commit()

    db.session.rollback()
    stmt = (
        db.select(SyncJob).where(
            SyncJob.idempotency_key == job_idempotency_key,
        )
    )
    lookup_job = db.session.execute(
        stmt
    ).scalar_one_or_none()

    assert lookup_job is not None


def test_other_connection_cannot_see_uncommitted_outer_transaction(test_transaction):
    username = "test_user_uncommit"
    email = "test_user_uncommit@email.invalid"

    new_user = User(username=username, email=email)
    new_user.set_password('peach_456')

    db.session.add(new_user)
    db.session.commit()

    stmt = (
        db.select(User).where(
            User.username == username,
        )
    )

    user_found = db.session.execute(
        stmt
    ).scalar_one_or_none()

    assert user_found is not None

    with db.engine.connect() as other_connection:
        user_not_found = other_connection.execute(
            stmt
        ).scalar_one_or_none()

        assert user_not_found is None
