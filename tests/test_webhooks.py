import hmac
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from demetra.app import app


class TestWebhookAPI:
    @pytest.fixture(autouse=True)
    def mock_queue(self):
        with patch("demetra.api.webhooks.queue.enqueue"):
            yield

    def test_returns_401_on_invalid_signature(self):
        with patch("demetra.services.github.GITHUB", {"webhook": {"secret": "mysecret"}}):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.post(
                "/api/v1/webhooks/github",
                json={"action": "created", "comment": {"body": "rebase"}},
                headers={
                    "X-GitHub-Event": "issue_comment",
                    "X-Hub-Signature-256": "sha256=invalid",
                },
            )
            assert response.status_code == 401
            assert response.json() == {"error": "Invalid signature"}

    def test_ignores_non_issue_comment_events(self):
        with patch("demetra.services.github.GITHUB", {"webhook": {"secret": None}}):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.post(
                "/api/v1/webhooks/github",
                json={},
                headers={"X-GitHub-Event": "push"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ignored"

    def test_accepts_valid_webhook_and_enqueues_job(self):
        with (
            patch("demetra.services.github.GITHUB", {"webhook": {"secret": None}}),
            patch("demetra.api.webhooks.queue.enqueue") as mock_enqueue,
        ):
            client = TestClient(app, raise_server_exceptions=False)
            payload = {
                "action": "created",
                "comment": {"body": "please rebase"},
                "issue": {
                    "number": 42,
                    "pull_request": {"url": "https://api.github.com/repo/pulls/42"},
                },
                "repository": {
                    "clone_url": "https://github.com/owner/repo.git",
                    "full_name": "owner/repo",
                },
            }
            response = client.post(
                "/api/v1/webhooks/github",
                json=payload,
                headers={"X-GitHub-Event": "issue_comment"},
            )
            assert response.status_code == 200
            assert response.json() == {"status": "accepted"}
            mock_enqueue.assert_called_once()

    def test_verifies_signature_with_secret(self):
        secret = "test_secret"
        payload_body = b'{"comment": {"body": "rebase"}}'
        expected_digest = hmac.new(key=secret.encode(), msg=payload_body, digestmod="sha256").hexdigest()

        with patch("demetra.services.github.GITHUB", {"webhook": {"secret": secret}}):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.post(
                "/api/v1/webhooks/github",
                content=payload_body,
                headers={
                    "X-GitHub-Event": "issue_comment",
                    "X-Hub-Signature-256": f"sha256={expected_digest}",
                    "Content-Type": "application/json",
                },
            )
            assert response.status_code == 200
