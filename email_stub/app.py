from flask import Flask, jsonify, request


app = Flask(__name__)

processed_keys = set()


@app.post("/emails")
def receive_email():
    idempotency_key = request.headers.get("Idempotency-Key")

    data = request.get_json(silent=True) or {}

    if not idempotency_key:
        return jsonify({"error": "Missing Idempotency-Key header"}), 400

    required_fields = ["to", "subject", "body"]
    if any(field not in data for field in required_fields):
        return jsonify({"error": "Missing required JSON fields (to, subject, body)"}), 400

    if idempotency_key in processed_keys:
        print(f"Duplicate request ignored (Key: {idempotency_key})")
        return "", 202

    processed_keys.add(idempotency_key)

    print(f"Accepted email to {data['to']} with subject '{data['subject']}'")

    return "", 202


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=4000,
    )
