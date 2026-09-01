import pytest
from datetime import datetime, timezone, timedelta

from models import db
from models.api_token import ApiToken
from models.user import User
from services.token_service import TokenService


@pytest.fixture
def token_user(app):
    user = User(
        username="alice",
        email="alice@example.com",
        password_hash="fake-hash",
    )
    db.session.add(user)
    db.session.commit()

    return user


def test_issue_token_stores_hash(token_user):
    user_id = token_user.id

    raw_token, api_token = TokenService.issue_token(
        user_id=user_id,
        name='Postman'
    )

    assert api_token.token_hash != raw_token
    assert api_token.token_hash == TokenService.hash_token(raw_token)

    stmt = db.select(ApiToken).where(
        ApiToken.token_hash == api_token.token_hash
    )
    result = db.session.execute(
        stmt
    ).scalar_one_or_none()

    assert result.token_id == api_token.token_id


def test_hash_token_is_deterministic():
    raw_token = "some-test-token"

    first_hash = TokenService.hash_token(raw_token)
    second_hash = TokenService.hash_token(raw_token)

    assert first_hash == second_hash


def test_resolve_valid_token(token_user):
    user_id = token_user.id

    # issue raw_token
    raw_token, api_token = TokenService.issue_token(
        user_id=user_id,
        name='Postman'
    )

    # confirm new token has never been used
    assert api_token.last_used_at is None

    # call TokenService.resolve_token(raw_token)
    resolved = TokenService.resolve_token(raw_token)
    assert resolved is not None

    # assert it resolved successfully
    assert resolved.token_id == api_token.token_id

    # assert correct user
    assert resolved.user_id == user_id

    # assert last_used_at was updated
    assert resolved.last_used_at is not None


def test_resolve_unknown_token(app):
    raw_token = "some-test-token"

    result = TokenService.resolve_token(raw_token)

    assert result is None


def test_resolve_expired_token(token_user):
    user_id = token_user.id

    # create a timezone-aware timestamp in the past
    expired_at = datetime.now(timezone.utc) - timedelta(minutes=5)

    # issue token with expires_at=that timestamp
    raw_token, api_token = TokenService.issue_token(
        user_id=user_id,
        name='Expired token',
        expires_at=expired_at
    )

    # confirm last_used_at starts as None
    assert api_token.last_used_at is None

    # attempt resolution
    resolved = TokenService.resolve_token(raw_token)

    # assert resolution failed
    assert resolved is None

    # reload database state
    token_id = api_token.token_id
    db.session.expire_all()
    stored_token = db.session.get(ApiToken, token_id)

    # assert last_used_at is still None
    assert stored_token.last_used_at is None
