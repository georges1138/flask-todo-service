from app import create_app
from services.email_client import EmailClient
from services.sync_job_worker import SyncJobWorker


def main():
    app = create_app()

    with app.app_context():
        email_service_url = app.config.get("EMAIL_SERVICE_URL")

        if not email_service_url:
            raise RuntimeError(
                "EMAIL_SERVICE_URL environment variable is required"
            )

        poll_interval_seconds = app.config["SYNC_JOB_POLL_INTERVAL_SECONDS"]

        with EmailClient(
                base_url=email_service_url,
        ) as email_client:
            worker = SyncJobWorker(
                email_client,
                poll_interval_seconds=poll_interval_seconds,
            )

            worker.run_forever()

if __name__ == "__main__":
    main()
