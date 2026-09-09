import pytest

from email_stub.app import app, processed_keys


@pytest.fixture
def client():
    processed_keys.clear()

    app.config["TESTING"] = True

    with app.test_client() as client:
        yield client

    processed_keys.clear()


def test_accepts_new_email_request(client):
    response = client.post(
        "/emails",
        headers={
            "Idempotency-Key": "job-123",
        },
        json={
            "to": "alice@example.com",
            "subject": "Todo completed",
            "body": "You completed: Buy milk",
        },
    )

    assert response.status_code == 202
    assert "job-123" in processed_keys


def test_duplicate_idempotency_key_is_accepted_without_duplicate_effect(client):
    payload = {
        "to": "alice@example.com",
        "subject": "Todo completed",
        "body": "You completed: Buy milk",
    }

    first_response = client.post(
        "/emails",
        headers={
            "Idempotency-Key": "job-123",
        },
        json=payload,
    )

    second_response = client.post(
        "/emails",
        headers={
            "Idempotency-Key": "job-123",
        },
        json=payload,
    )

    assert first_response.status_code == 202
    assert second_response.status_code == 202
    assert len(processed_keys) == 1
    assert "job-123" in processed_keys


def test_missing_idempotency_key_returns_400(client):
    response = client.post(
        "/emails",
        json={
            "to": "alice@example.com",
            "subject": "Todo completed",
            "body": "You completed: Buy milk",
        },
    )

    assert response.status_code == 400
    assert len(processed_keys) == 0

    response_data = response.get_json()
    assert "Idempotency-Key" in response_data["error"]


def test_missing_required_json_field_returns_400(client):
    response = client.post(
        "/emails",
        headers={
            "Idempotency-Key": "job-789",
        },
        json={
            "to": "alice@example.com",
            "subject": "Todo completed",
            # body intentionally missing
        },
    )

    assert response.status_code == 400
    assert len(processed_keys) == 0

    response_data = response.get_json()
    assert "Missing required JSON fields" in response_data["error"]
