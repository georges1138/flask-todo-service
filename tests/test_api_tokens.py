import pytest

from models import db
from models.api_token import ApiToken
from services.user_service import UserService
from services.token_service import TokenService


@pytest.fixture
def api_user(app):
    username = "alice"
    email = "alice@example.com"
    password = "correct-password"

    user = UserService.register(
        username,
        email,
        password,
    )

    return {
        "user": user,
        "username": username,
        "password": password,
    }


def test_token_endpoint_rejects_invalid_credentials_without_session(client):
    response = client.post(
        "/api/v1/tokens",
        json={
            "username": "does-not-exist",
            "password": "wrong-password",
            "name": "Postman",
        }
    )

    assert response.status_code == 401
    assert response.is_json
    data = response.get_json()
    assert data["error"] == "Invalid username or password"


def test_token_endpoint_creates_token_with_valid_credentials(
    client,
    api_user
):
    response = client.post(
        "/api/v1/tokens",
        json={
            "username": api_user["username"],
            "password": api_user["password"],
            "name": "Postman",
        }
    )

    assert response.status_code == 201

    data = response.get_json()

    assert "token" in data
    assert "token_id" in data
    assert "name" in data
    assert data["name"] == "Postman"

    raw_token = data["token"]
    token_id = data["token_id"]

    stored_token = db.session.get(ApiToken, token_id)

    assert stored_token is not None
    assert stored_token.user_id == api_user["user"].id
    assert stored_token.name == "Postman"
    assert stored_token.token_hash != raw_token
    assert stored_token.token_hash == TokenService.hash_token(raw_token)
