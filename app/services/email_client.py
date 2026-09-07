import httpx


class EmailClient:
    def __init__(self, base_url, timeout_seconds=5, client=None):
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds

        if client is not None:
            self.client = client
        else:
            self.client = httpx.Client(
                base_url=self.base_url,
                timeout=self.timeout_seconds
            )

    def send_email(
        self,
        to,
        subject,
        body,
        idempotency_key,
    ):
        payload = {
            "to": to,
            "subject": subject,
            "body": body,
        }

        headers = {
            "Idempotency-Key": idempotency_key
        }

        response = self.client.post("/emails", json=payload, headers=headers)

        response.raise_for_status()

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
