import httpx
import time

from services.sync_job_service import SyncJobService


class SyncJobWorker:
    def __init__(self,
                 email_client,
                 poll_interval_seconds=1,
                 max_attempts=3,
                 base_delay_seconds=2,
                 ):
        self.email_client = email_client
        self.poll_interval_seconds = poll_interval_seconds
        self.max_attempts = max_attempts
        self.base_delay_seconds = base_delay_seconds

    def run_once(self):
        job = SyncJobService.claim_next_job()

        if job is None:
            return False

        try:
            self.email_client.send_email(
                to=job.email_address,
                subject="Todo completed",
                body=f"You completed: {job.todo_title}",
                idempotency_key=job.idempotency_key,
            )
        except httpx.HTTPError as error:
            SyncJobService.schedule_retry_or_fail(
                job,
                error=error,
                max_attempts=self.max_attempts,
                base_delay_seconds=self.base_delay_seconds,
            )
        else:
            SyncJobService.mark_succeeded(job)
        return True

    def run_forever(self):
        while True:
            processed = self.run_once()

            if not processed:
                time.sleep(self.poll_interval_seconds)
