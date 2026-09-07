import pytest
import json

import httpx

from services.email_client import EmailClient


def test_send_email_builds_expected_http_request():
    captured = {}

    def handler(request):
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["idempotency_key"] = request.headers.get("Idempotency-Key")
        captured["body"] = json.loads(request.content)

        return httpx.Response(
            200,
            request=request,
        )

    transport = httpx.MockTransport(handler)

    test_http_client = httpx.Client(
        base_url="http://email-service.test",
        transport=transport,
    )

    email_client = EmailClient(
        base_url="http://email-service.test",
        client=test_http_client,
    )

    result = email_client.send_email(
        to="alice@example.com",
        subject="Todo completed",
        body="You completed: Buy milk",
        idempotency_key="job-123",
    )

    assert result is None
    assert captured["method"] == "POST"
    assert captured["url"] == "http://email-service.test/emails"
    assert captured["idempotency_key"] == "job-123"
    assert captured["body"] == {
        "to": "alice@example.com",
        "subject": "Todo completed",
        "body": "You completed: Buy milk",
    }

    email_client.close()


def test_send_email_raises_for_http_error():
    def handler(request):
        return httpx.Response(
            503,
            request=request,
        )

    transport = httpx.MockTransport(handler)

    test_http_client = httpx.Client(
        base_url="http://email-service.test",
        transport=transport,
    )

    email_client = EmailClient(
        base_url="http://email-service.test",
        client=test_http_client,
    )

    with pytest.raises(httpx.HTTPStatusError):
        email_client.send_email(
            to="bob@example.com",
            subject="System Alert",
            body="Checking error handling",
            idempotency_key="job-456"
        )

    email_client.close()


def test_send_email_propagates_timeout():
    def handler(request):
        raise httpx.ReadTimeout(
            "email service timed out",
            request=request,
        )

    transport = httpx.MockTransport(handler)

    test_http_client = httpx.Client(
        base_url="http://email-service.test",
        transport=transport,
    )

    email_client = EmailClient(
        base_url="http://email-service.test",
        client=test_http_client,
    )

    with pytest.raises(httpx.ReadTimeout):
        email_client.send_email(
            to="bob@example.com",
            subject="System Alert",
            body="Checking error handling",
            idempotency_key="job-456"
        )

    email_client.close()
