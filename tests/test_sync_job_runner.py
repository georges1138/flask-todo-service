import pytest

from flask import Flask
from services.sync_job_runner import main


def test_main_fails_when_email_service_url_missing(monkeypatch):
    fake_app = Flask(__name__)

    fake_app.config["EMAIL_SERVICE_URL"] = None
    fake_app.config["SYNC_JOB_POLL_INTERVAL_SECONDS"] = 1

    monkeypatch.setattr(
        "services.sync_job_runner.create_app",
        lambda: fake_app,
    )

    with pytest.raises(RuntimeError, match="EMAIL_SERVICE_URL"):
        main()


def test_main_wires_email_client_and_worker(monkeypatch):
    fake_app = Flask(__name__)
    fake_app.config["EMAIL_SERVICE_URL"] = "http://email-service.test"
    fake_app.config["SYNC_JOB_POLL_INTERVAL_SECONDS"] = 7
    captured = {}

    class FakeEmailClient:
        def __init__(self, base_url):
            self.base_url = base_url
            captured["email_client_base_url"] = base_url
            captured["email_client_instance"] = self

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    class FakeSyncJobWorker:
        def __init__(self, email_client, poll_interval_seconds):
            captured["worker_email_client"] = email_client
            captured["poll_interval_seconds"] = poll_interval_seconds

        def run_forever(self):
            captured["run_forever_called"] = True

    monkeypatch.setattr(
        "services.sync_job_runner.create_app",
        lambda: fake_app,
    )

    monkeypatch.setattr(
        "services.sync_job_runner.EmailClient",
        FakeEmailClient,
    )

    monkeypatch.setattr(
        "services.sync_job_runner.SyncJobWorker",
        FakeSyncJobWorker,
    )

    main()
    assert captured["email_client_base_url"] == "http://email-service.test"

    assert (
            captured["worker_email_client"]
            is captured["email_client_instance"]
    )

    assert captured["poll_interval_seconds"] == 7

    assert captured["run_forever_called"] is True
