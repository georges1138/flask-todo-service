import pytest

from models import db
from models.user import User
from services.user_service import UserService


@pytest.fixture
def user_scenario(app):
    password = "test_password"

    exist_user = User(
        username="existing_user",
        email="existing_user@example.com"
    )

    exist_user.set_password(password)

    db.session.add(exist_user)
    db.session.commit()

    return {
        "exist_user": exist_user,
        "password": password,
    }


def test_register_new_user(app):
    username = "test_user"
    email = "test_user@example.com"
    password = "test_password"

    result = UserService.register(
        username=username,
        email=email,
        password=password,
    )

    assert result is not None

    db.session.expire_all()

    stmt = db.select(User).where(
        User.username == username
    )

    new_user = db.session.execute(
        stmt
    ).scalar_one_or_none()

    assert new_user is not None
    assert new_user.check_password(password)
    assert new_user.email == email


def test_register_dup_user(user_scenario):
    exist_user = user_scenario["exist_user"]
    password = user_scenario["password"]

    result = UserService.register(
        username=exist_user.username,
        email="not_exist_user@example.com",
        password=password,
    )

    assert result is None


def test_register_duplicate_email(user_scenario):
    exist_user = user_scenario["exist_user"]

    result = UserService.register(
        username="not_exist_user",
        email=exist_user.email,
        password="another_password",
    )

    assert result is None


def test_login_succeeds(user_scenario):
    exist_user = user_scenario["exist_user"]
    password = user_scenario["password"]

    result = UserService.login(
        username=exist_user.username,
        password=password
    )

    assert result.id == exist_user.id


def test_login_fails_existing_user(user_scenario):
    exist_user = user_scenario["exist_user"]
    password = "not-the-password"

    result = UserService.login(
        username=exist_user.username,
        password=password
    )

    assert result is None


def test_login_fails_unknown_user(user_scenario):
    user = "not-the-user"
    password = "not-the-password"

    result = UserService.login(
        username=user,
        password=password
    )

    assert result is None
