import json
import os
import ssl
import subprocess
import threading
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from redis.exceptions import RedisError
from rq.exceptions import DuplicateJobError

from demetra.library.models import Session
from demetra.services.daemons.listener import (
    extract_pr_info,
    fetch_subject_body,
    fetch_subject_comment,
    get_notifications,
    is_coderabbit_author,
    mentions_demetra_ai_and_merge,
    mentions_demetra_ai_and_rebase,
    process_coderabbit_comments_notification,
    process_merge_notification,
    process_rebase_notification,
    should_process_notification,
)
from demetra.settings import GITHUB


class _CommentHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({"body": "a finding", "user": {"login": "coderabbitai[bot]"}, "id": 42}).encode()
        self.send_response(code=200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _start_gh_api_stub(tmp_path: Path) -> tuple[HTTPServer, threading.Thread, Path]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(UTC) - timedelta(days=1))
        .not_valid_after(datetime.now(UTC) + timedelta(days=1))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost")]), critical=False)
        .sign(key, hashes.SHA256())
    )
    cert_path = tmp_path / "cert.pem"
    key_path = tmp_path / "key.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    server = HTTPServer(("127.0.0.1", 0), _CommentHandler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(certfile=cert_path, keyfile=key_path)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, cert_path


class TestGetNotifications:
    @pytest.mark.asyncio
    async def test_returns_empty_list_on_api_error(self):
        with patch("demetra.services.daemons.listener.run_command_to_file", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (1, "", "API error")
            result = await get_notifications()
            assert result == []

    @pytest.mark.asyncio
    async def test_returns_empty_list_on_empty_response(self):
        with patch("demetra.services.daemons.listener.run_command_to_file", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (0, "", "")
            result = await get_notifications()
            assert result == []

    @pytest.mark.asyncio
    async def test_returns_parsed_notifications(self):
        notifications = [
            {
                "id": "1",
                "reason": "mention",
                "subject": {"type": "PullRequest", "url": "https://api.github.com/repos/owner/repo/pulls/42"},
            }
        ]
        with patch("demetra.services.daemons.listener.run_command_to_file", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (0, json.dumps(notifications), "")
            result = await get_notifications()
            assert result == notifications

    @pytest.mark.asyncio
    async def test_handles_invalid_json(self):
        with patch("demetra.services.daemons.listener.run_command_to_file", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (0, "invalid json", "")
            result = await get_notifications()
            assert result == []


class TestShouldProcessNotification:
    def test_processes_mention_reason(self):
        assert should_process_notification({"reason": "mention"}) is True

    def test_processes_subscribed_reason(self):
        assert should_process_notification({"reason": "subscribed"}) is True

    def test_ignores_other_reasons(self):
        assert should_process_notification({"reason": "assign"}) is False
        assert should_process_notification({"reason": "review_requested"}) is False
        assert should_process_notification({"reason": "author"}) is False

    def test_handles_missing_reason(self):
        assert should_process_notification({}) is False


class TestExtractPrInfo:
    def test_extracts_from_pull_request(self):
        notification = {
            "subject": {
                "type": "PullRequest",
                "url": "https://api.github.com/repos/owner/repo/pulls/42",
                "title": "Fix the thing",
            },
            "repository": {
                "full_name": "owner/repo",
                "clone_url": "https://github.com/owner/repo.git",
                "html_url": "https://github.com/owner/repo",
            },
        }
        result = extract_pr_info(notification)
        assert result == {
            "pr_number": 42,
            "full_name": "owner/repo",
            "title": "Fix the thing",
        }

    def test_returns_none_for_non_pr(self):
        notification = {
            "subject": {"type": "Issue", "url": "https://api.github.com/repos/owner/repo/issues/1"},
            "repository": {"full_name": "owner/repo", "clone_url": "https://github.com/owner/repo.git"},
        }
        assert extract_pr_info(notification) is None

    def test_returns_none_for_commit(self):
        notification = {
            "subject": {"type": "Commit", "url": "https://api.github.com/repos/owner/repo/commits/abc123"},
            "repository": {"full_name": "owner/repo", "clone_url": "https://github.com/owner/repo.git"},
        }
        assert extract_pr_info(notification) is None

    def test_returns_none_without_subject_type(self):
        notification = {
            "repository": {"full_name": "owner/repo", "clone_url": "https://github.com/owner/repo.git"},
        }
        assert extract_pr_info(notification) is None

    def test_returns_none_without_full_name(self):
        notification = {
            "subject": {"type": "PullRequest", "url": "https://api.github.com/repos/owner/repo/pulls/42"},
            "repository": {"clone_url": "https://github.com/owner/repo.git"},
        }
        assert extract_pr_info(notification) is None


class TestFetchSubjectBody:
    @pytest.mark.asyncio
    async def test_fetches_comment_body(self):
        subject = {
            "title": "PR Title",
            "latest_comment_url": "https://api.github.com/repos/owner/repo/issues/comments/123",
        }
        with patch("demetra.services.daemons.listener.run_command_to_file", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (
                0,
                json.dumps({"body": "demetra-ai please rebase", "author": "manti-by", "id": 1}),
                "",
            )
            result = await fetch_subject_body(subject)
            assert result == "demetra-ai please rebase"

    @pytest.mark.asyncio
    async def test_falls_back_to_title_when_no_comment_url(self):
        subject = {"title": "Simple title"}
        result = await fetch_subject_body(subject)
        assert result == "Simple title"

    @pytest.mark.asyncio
    async def test_falls_back_to_title_on_api_error(self):
        subject = {
            "title": "Title",
            "latest_comment_url": "https://api.github.com/repos/owner/repo/issues/comments/123",
        }
        with patch("demetra.services.daemons.listener.run_command_to_file", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (1, "", "Not found")
            result = await fetch_subject_body(subject)
            assert result == "Title"

    @pytest.mark.asyncio
    async def test_falls_back_to_title_when_body_empty(self):
        subject = {
            "title": "Title",
            "latest_comment_url": "https://api.github.com/repos/owner/repo/issues/comments/123",
        }
        with patch("demetra.services.daemons.listener.run_command_to_file", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (0, json.dumps({"body": "", "author": "coderabbitai[bot]", "id": 1}), "")
            result = await fetch_subject_body(subject)
            assert result == "Title"


class TestFetchSubjectComment:
    @pytest.mark.asyncio
    async def test_parses_body_author_and_id(self):
        subject = {"title": "PR Title", "latest_comment_url": "https://api.github.com/repos/owner/repo/comments/1"}
        with patch("demetra.services.daemons.listener.run_command_to_file", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (
                0,
                json.dumps({"body": "  a finding  ", "author": "coderabbitai[bot]", "id": 42}),
                "",
            )
            result = await fetch_subject_comment(subject)
            assert result == {"body": "a finding", "author": "coderabbitai[bot]", "id": "42"}
            assert mock_run.await_args is not None
            assert mock_run.await_args.kwargs["command"][-1] == "{body: .body, author: .user.login, id: .id}"

    @pytest.mark.asyncio
    async def test_gh_api_accepts_the_subject_comment_filter(self, tmp_path):
        subject = {"title": "PR Title", "latest_comment_url": "https://api.github.com/repos/owner/repo/comments/1"}
        with patch("demetra.services.daemons.listener.run_command_to_file", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (0, json.dumps({"body": "a finding", "author": "coderabbitai[bot]", "id": 42}), "")
            await fetch_subject_comment(subject)
            assert mock_run.await_args is not None
            jq_filter = mock_run.await_args.kwargs["command"][-1]

        config_dir = tmp_path / "gh-config"
        config_dir.mkdir()
        server, thread, cert_path = _start_gh_api_stub(tmp_path)
        env = {
            **os.environ,
            "GH_CONFIG_DIR": str(config_dir),
            "GH_HOST": f"localhost:{server.server_port}",
            "GH_ENTERPRISE_TOKEN": "test",
            "SSL_CERT_FILE": str(cert_path),
            "GH_NO_UPDATE_NOTIFIER": "1",
            "GH_PROMPT_DISABLED": "1",
        }
        try:
            result = subprocess.run(
                args=[str(GITHUB["path"]), "api", "/repos/o/r/issues/comments/1", "--jq", jq_filter],
                env=env,
                capture_output=True,
                text=True,
                timeout=15,
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout) == {"body": "a finding", "author": "coderabbitai[bot]", "id": 42}

    @pytest.mark.asyncio
    async def test_returns_title_fallback_without_comment_url(self):
        result = await fetch_subject_comment({"title": "Title"})
        assert result == {"body": "Title", "author": "", "id": ""}

    @pytest.mark.asyncio
    async def test_returns_title_fallback_on_api_error(self):
        subject = {"title": "Title", "latest_comment_url": "https://api.github.com/repos/owner/repo/comments/1"}
        with patch("demetra.services.daemons.listener.run_command_to_file", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (1, "", "Not found")
            assert await fetch_subject_comment(subject) == {"body": "Title", "author": "", "id": ""}

    @pytest.mark.asyncio
    async def test_returns_title_fallback_on_invalid_json(self):
        subject = {"title": "Title", "latest_comment_url": "https://api.github.com/repos/owner/repo/comments/1"}
        with patch("demetra.services.daemons.listener.run_command_to_file", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (0, "invalid json", "")
            assert await fetch_subject_comment(subject) == {"body": "Title", "author": "", "id": ""}

    @pytest.mark.asyncio
    async def test_preserves_author_when_body_is_empty(self):
        subject = {"title": "Title", "latest_comment_url": "https://api.github.com/repos/owner/repo/comments/1"}
        with patch("demetra.services.daemons.listener.run_command_to_file", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (0, json.dumps({"body": "", "author": "coderabbitai[bot]", "id": 7}), "")
            assert await fetch_subject_comment(subject) == {"body": "Title", "author": "coderabbitai[bot]", "id": "7"}


class TestMentionsDemetraAiAndMerge:
    def test_returns_true_when_both_present(self):
        assert mentions_demetra_ai_and_merge("@demetra-ai please merge") is True

    def test_returns_true_case_insensitive(self):
        assert mentions_demetra_ai_and_merge("@DEMETRA-AI MERGE") is True

    def test_returns_false_without_at_mention(self):
        assert mentions_demetra_ai_and_merge("DEMETRA-AI MERGE") is False

    def test_returns_false_when_only_rebase(self):
        assert mentions_demetra_ai_and_merge("please rebase") is False

    def test_returns_false_when_only_demetra_ai(self):
        assert mentions_demetra_ai_and_merge("@demetra-ai help") is False

    def test_returns_false_when_none_present(self):
        assert mentions_demetra_ai_and_merge("looks good to me") is False

    def test_returns_false_when_merge_not_directed_at_bot(self):
        assert mentions_demetra_ai_and_merge("thanks @demetra-ai, I'll merge this myself later") is False

    def test_returns_true_with_comma_after_mention(self):
        assert mentions_demetra_ai_and_merge("@demetra-ai, merge") is True
        assert mentions_demetra_ai_and_merge("@demetra-ai merge please") is True

    def test_returns_false_for_none(self):
        assert mentions_demetra_ai_and_merge(None) is False

    def test_returns_false_for_empty_string(self):
        assert mentions_demetra_ai_and_merge("") is False


class TestMentionsDemetraAiAndRebase:
    def test_returns_true_when_both_present(self):
        assert mentions_demetra_ai_and_rebase("@demetra-ai please rebase") is True

    def test_returns_true_case_insensitive(self):
        assert mentions_demetra_ai_and_rebase("@DEMETRA-AI REBASE") is True

    def test_returns_false_without_at_mention(self):
        assert mentions_demetra_ai_and_rebase("DEMETRA-AI REBASE") is False

    def test_returns_false_when_only_merge(self):
        assert mentions_demetra_ai_and_rebase("please merge") is False

    def test_returns_false_when_only_demetra_ai(self):
        assert mentions_demetra_ai_and_rebase("@demetra-ai help") is False

    def test_returns_false_when_none_present(self):
        assert mentions_demetra_ai_and_rebase("looks good to me") is False

    def test_returns_false_when_rebase_not_directed_at_bot(self):
        assert mentions_demetra_ai_and_rebase("thanks @demetra-ai, I'll rebase this myself later") is False

    def test_returns_true_with_comma_after_mention(self):
        assert mentions_demetra_ai_and_rebase("@demetra-ai, rebase") is True
        assert mentions_demetra_ai_and_rebase("@demetra-ai rebase please") is True

    def test_returns_false_for_none(self):
        assert mentions_demetra_ai_and_rebase(None) is False

    def test_returns_false_for_empty_string(self):
        assert mentions_demetra_ai_and_rebase("") is False

    def test_does_not_match_merge_when_rebase_requested(self):
        assert mentions_demetra_ai_and_rebase("@demetra-ai merge") is False

    def test_does_not_match_rebase_in_other_context(self):
        assert mentions_demetra_ai_and_rebase("can you rebase this branch?") is False

    def test_matches_with_colon_separator(self):
        assert mentions_demetra_ai_and_rebase("@demetra-ai: rebase") is True


class TestProcessMergeNotification:
    PR_INFO = {"pr_number": 42, "full_name": "owner/repo", "title": "Fix the thing"}

    @pytest.mark.asyncio
    async def test_returns_false_when_no_session_found(self):
        with (
            patch("demetra.services.daemons.listener.get_session_by_pr_link", new_callable=AsyncMock) as mock_db,
            patch("demetra.services.daemons.listener.increment_listener_attempts", new_callable=AsyncMock) as mock_inc,
        ):
            mock_db.return_value = None
            result = await process_merge_notification(self.PR_INFO)
            assert result is False
            mock_inc.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_returns_false_when_session_has_no_project_id(self):
        session = Session(
            task_id="TASK-123",
            build_plan="plan",
            posted_to_linear=True,
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
            pr_link="https://github.com/owner/repo/pull/42",
            project_id=None,
        )
        with (
            patch("demetra.services.daemons.listener.get_session_by_pr_link", new_callable=AsyncMock) as mock_db,
            patch("demetra.services.daemons.listener.increment_listener_attempts", new_callable=AsyncMock) as mock_inc,
            patch("demetra.services.daemons.listener.reset_listener_attempts", new_callable=AsyncMock) as mock_reset,
            patch("demetra.services.daemons.listener.queue") as mock_queue,
        ):
            mock_db.return_value = session
            mock_inc.return_value = 1
            result = await process_merge_notification(self.PR_INFO)
            assert result is False
            mock_queue.enqueue.assert_not_called()
            mock_reset.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_enqueues_merge_workflow(self):
        session = Session(
            task_id="TASK-123",
            build_plan="Implement feature X",
            posted_to_linear=True,
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
            pr_link="https://github.com/owner/repo/pull/42",
            project_id="proj-123",
        )
        with (
            patch("demetra.services.daemons.listener.get_session_by_pr_link", new_callable=AsyncMock) as mock_db,
            patch("demetra.services.daemons.listener.increment_listener_attempts", new_callable=AsyncMock) as mock_inc,
            patch("demetra.services.daemons.listener.reset_listener_attempts", new_callable=AsyncMock) as mock_reset,
            patch("demetra.services.daemons.listener.queue") as mock_queue,
        ):
            mock_db.return_value = session
            mock_inc.return_value = 1

            result = await process_merge_notification(self.PR_INFO)

            assert result is True
            mock_queue.enqueue.assert_called_once_with(
                mock_queue.enqueue.call_args[0][0],
                task_id=session.task_id,
                project_id=session.project_id,
                pr_number=42,
                full_name="owner/repo",
            )
            mock_reset.assert_awaited_once_with(session.task_id)

    @pytest.mark.asyncio
    async def test_marks_read_when_max_listener_attempts_exceeded(self):
        session = Session(
            task_id="TASK-123",
            build_plan="plan",
            posted_to_linear=True,
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
            pr_link="https://github.com/owner/repo/pull/42",
            project_id="proj-123",
        )
        with (
            patch("demetra.services.daemons.listener.get_session_by_pr_link", new_callable=AsyncMock) as mock_db,
            patch("demetra.services.daemons.listener.increment_listener_attempts", new_callable=AsyncMock) as mock_inc,
            patch("demetra.services.daemons.listener.reset_listener_attempts", new_callable=AsyncMock) as mock_reset,
            patch("demetra.services.daemons.listener.queue") as mock_queue,
            patch("demetra.services.daemons.listener.MAX_ATTEMPTS", {"listener": 3}),
        ):
            mock_db.return_value = session
            mock_inc.return_value = 4

            result = await process_merge_notification(self.PR_INFO)

            assert result is True
            mock_queue.enqueue.assert_not_called()
            mock_reset.assert_not_awaited()


class TestProcessRebaseNotification:
    PR_INFO = {"pr_number": 42, "full_name": "owner/repo", "title": "Fix the thing"}

    @pytest.mark.asyncio
    async def test_returns_false_when_no_session_found(self):
        with (
            patch("demetra.services.daemons.listener.get_session_by_pr_link", new_callable=AsyncMock) as mock_db,
            patch("demetra.services.daemons.listener.increment_listener_attempts", new_callable=AsyncMock) as mock_inc,
        ):
            mock_db.return_value = None
            result = await process_rebase_notification(self.PR_INFO)
            assert result is False
            mock_inc.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_returns_false_when_session_has_no_project_id(self):
        session = Session(
            task_id="TASK-123",
            build_plan="plan",
            posted_to_linear=True,
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
            pr_link="https://github.com/owner/repo/pull/42",
            project_id=None,
        )
        with (
            patch("demetra.services.daemons.listener.get_session_by_pr_link", new_callable=AsyncMock) as mock_db,
            patch("demetra.services.daemons.listener.increment_listener_attempts", new_callable=AsyncMock) as mock_inc,
            patch("demetra.services.daemons.listener.reset_listener_attempts", new_callable=AsyncMock) as mock_reset,
            patch("demetra.services.daemons.listener.queue") as mock_queue,
        ):
            mock_db.return_value = session
            mock_inc.return_value = 1
            result = await process_rebase_notification(self.PR_INFO)
            assert result is False
            mock_queue.enqueue.assert_not_called()
            mock_reset.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_enqueues_rebase_workflow(self):
        session = Session(
            task_id="TASK-123",
            build_plan="Implement feature X",
            posted_to_linear=True,
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
            pr_link="https://github.com/owner/repo/pull/42",
            project_id="proj-123",
        )
        with (
            patch("demetra.services.daemons.listener.get_session_by_pr_link", new_callable=AsyncMock) as mock_db,
            patch("demetra.services.daemons.listener.increment_listener_attempts", new_callable=AsyncMock) as mock_inc,
            patch("demetra.services.daemons.listener.reset_listener_attempts", new_callable=AsyncMock) as mock_reset,
            patch("demetra.services.daemons.listener.queue") as mock_queue,
        ):
            mock_db.return_value = session
            mock_inc.return_value = 1

            result = await process_rebase_notification(self.PR_INFO)

            assert result is True
            mock_queue.enqueue.assert_called_once_with(
                mock_queue.enqueue.call_args[0][0],
                task_id=session.task_id,
                project_id=session.project_id,
                pr_number=42,
                full_name="owner/repo",
            )
            mock_reset.assert_awaited_once_with(session.task_id)

    @pytest.mark.asyncio
    async def test_marks_read_when_max_listener_attempts_exceeded(self):
        session = Session(
            task_id="TASK-123",
            build_plan="plan",
            posted_to_linear=True,
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
            pr_link="https://github.com/owner/repo/pull/42",
            project_id="proj-123",
        )
        with (
            patch("demetra.services.daemons.listener.get_session_by_pr_link", new_callable=AsyncMock) as mock_db,
            patch("demetra.services.daemons.listener.increment_listener_attempts", new_callable=AsyncMock) as mock_inc,
            patch("demetra.services.daemons.listener.reset_listener_attempts", new_callable=AsyncMock) as mock_reset,
            patch("demetra.services.daemons.listener.queue") as mock_queue,
            patch("demetra.services.daemons.listener.MAX_ATTEMPTS", {"listener": 3}),
        ):
            mock_db.return_value = session
            mock_inc.return_value = 4

            result = await process_rebase_notification(self.PR_INFO)

            assert result is True
            mock_queue.enqueue.assert_not_called()
            mock_reset.assert_not_awaited()


class TestIsCoderabbitAuthor:
    def test_matches_bot_login_case_insensitively(self):
        assert is_coderabbit_author("coderabbitai[bot]") is True
        assert is_coderabbit_author("@CodeRabbitAI") is True

    def test_ignores_other_authors(self):
        assert is_coderabbit_author("manti-by") is False
        assert is_coderabbit_author(None) is False
        assert is_coderabbit_author("") is False


class TestProcessCoderabbitCommentsNotification:
    PR_INFO = {"pr_number": 42, "full_name": "owner/repo", "title": "Fix the thing"}

    @pytest.fixture(autouse=True)
    def no_pending_batch(self):
        with patch("demetra.services.daemons.listener.load_pending_comments", return_value=None):
            yield

    COMMENTS = [
        {"thread_id": "THREAD_1", "body": "first finding", "path": "a.py"},
        {"thread_id": "THREAD_2", "body": "second finding", "path": "b.py"},
    ]

    @staticmethod
    def _session(project_id: str | None = "proj-123") -> Session:
        return Session(
            task_id="TASK-123",
            build_plan="plan",
            posted_to_linear=True,
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
            pr_link="https://github.com/owner/repo/pull/42",
            project_id=project_id,
        )

    @pytest.mark.asyncio
    async def test_returns_false_when_no_session_found(self):
        with (
            patch("demetra.services.daemons.listener.get_session_by_pr_link", new_callable=AsyncMock) as mock_db,
            patch("demetra.services.daemons.listener.increment_listener_attempts", new_callable=AsyncMock),
        ):
            mock_db.return_value = None
            assert await process_coderabbit_comments_notification(self.PR_INFO) is False

    @pytest.mark.asyncio
    async def test_returns_false_when_session_has_no_project_id(self):
        with (
            patch("demetra.services.daemons.listener.get_session_by_pr_link", new_callable=AsyncMock) as mock_db,
            patch(
                "demetra.services.daemons.listener.increment_listener_attempts", new_callable=AsyncMock, return_value=1
            ),
            patch("demetra.services.daemons.listener.queue") as mock_queue,
        ):
            mock_db.return_value = self._session(project_id=None)
            assert await process_coderabbit_comments_notification(self.PR_INFO) is False
            mock_queue.enqueue.assert_not_called()

    @pytest.mark.asyncio
    async def test_saves_all_comments_and_enqueues_one_workflow(self):
        with (
            patch("demetra.services.daemons.listener.get_session_by_pr_link", new_callable=AsyncMock) as mock_db,
            patch(
                "demetra.services.daemons.listener.increment_listener_attempts", new_callable=AsyncMock, return_value=1
            ),
            patch("demetra.services.daemons.listener.reset_listener_attempts", new_callable=AsyncMock) as mock_reset,
            patch("demetra.services.daemons.listener.get_coderabbit_comments", new_callable=AsyncMock) as mock_comments,
            patch("demetra.services.daemons.listener.save_pending_comments", return_value=True) as mock_save,
            patch("demetra.services.daemons.listener.queue") as mock_queue,
        ):
            mock_db.return_value = self._session()
            mock_comments.return_value = self.COMMENTS

            assert await process_coderabbit_comments_notification(self.PR_INFO) is True

            batch = mock_save.call_args.kwargs["comments"]
            assert batch["pr_number"] == 42
            assert batch["full_name"] == "owner/repo"
            assert batch["comments"] == self.COMMENTS
            assert batch["task_id"] == "TASK-123"
            assert batch["project_id"] == "proj-123"
            assert batch["attempt"] == 0
            assert batch["batch_id"]
            mock_queue.enqueue.assert_called_once_with(
                mock_queue.enqueue.call_args[0][0],
                job_id=f"demetra:comments:{batch['batch_id']}:0",
                unique=True,
                task_id="TASK-123",
                project_id="proj-123",
                pr_number=42,
                full_name="owner/repo",
            )
            from demetra.workflows.comments import run_comments_workflow

            assert mock_queue.enqueue.call_args[0][0] is run_comments_workflow
            mock_reset.assert_awaited_once_with("TASK-123")

    @pytest.mark.asyncio
    async def test_pending_batch_resumes_submission_without_spending_attempt_budget(self):
        pending = {
            "batch_id": "batch-1",
            "task_id": "TASK-123",
            "project_id": "proj-123",
            "pr_number": 42,
            "full_name": "owner/repo",
            "comments": self.COMMENTS,
            "attempt": 1,
        }
        with (
            patch("demetra.services.daemons.listener.get_session_by_pr_link", new_callable=AsyncMock) as mock_db,
            patch("demetra.services.daemons.listener.load_pending_comments", return_value=pending),
            patch("demetra.services.daemons.listener.increment_listener_attempts", new_callable=AsyncMock) as mock_inc,
            patch("demetra.services.daemons.listener.reset_listener_attempts", new_callable=AsyncMock) as mock_reset,
            patch("demetra.services.daemons.listener.get_coderabbit_comments", new_callable=AsyncMock) as mock_comments,
            patch("demetra.services.daemons.listener.queue") as mock_queue,
        ):
            mock_db.return_value = self._session()

            assert await process_coderabbit_comments_notification(self.PR_INFO) is False

            mock_queue.enqueue.assert_called_once_with(
                mock_queue.enqueue.call_args[0][0],
                job_id="demetra:comments:batch-1:1",
                unique=True,
                task_id="TASK-123",
                project_id="proj-123",
                pr_number=42,
                full_name="owner/repo",
            )
            mock_inc.assert_not_awaited()
            mock_reset.assert_not_awaited()
            mock_comments.assert_not_awaited()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("error", [RedisError("connection refused"), DuplicateJobError("already submitted")])
    async def test_failed_or_duplicate_enqueue_leaves_notification_unread(self, error):
        with (
            patch("demetra.services.daemons.listener.get_session_by_pr_link", new_callable=AsyncMock) as mock_db,
            patch(
                "demetra.services.daemons.listener.increment_listener_attempts", new_callable=AsyncMock, return_value=1
            ),
            patch("demetra.services.daemons.listener.reset_listener_attempts", new_callable=AsyncMock) as mock_reset,
            patch("demetra.services.daemons.listener.get_coderabbit_comments", new_callable=AsyncMock) as mock_comments,
            patch("demetra.services.daemons.listener.save_pending_comments", return_value=True),
            patch("demetra.services.daemons.listener.queue") as mock_queue,
        ):
            mock_db.return_value = self._session()
            mock_comments.return_value = self.COMMENTS
            mock_queue.enqueue.side_effect = error

            assert await process_coderabbit_comments_notification(self.PR_INFO) is False
            mock_reset.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_pending_batch_skips_attempt_budget_without_enqueue(self):
        with (
            patch("demetra.services.daemons.listener.get_session_by_pr_link", new_callable=AsyncMock) as mock_db,
            patch("demetra.services.daemons.listener.load_pending_comments", return_value={"comments": self.COMMENTS}),
            patch("demetra.services.daemons.listener.increment_listener_attempts", new_callable=AsyncMock) as mock_inc,
            patch("demetra.services.daemons.listener.reset_listener_attempts", new_callable=AsyncMock) as mock_reset,
            patch("demetra.services.daemons.listener.get_coderabbit_comments", new_callable=AsyncMock) as mock_comments,
            patch("demetra.services.daemons.listener.queue") as mock_queue,
        ):
            mock_db.return_value = self._session()

            assert await process_coderabbit_comments_notification(self.PR_INFO) is False

            mock_inc.assert_not_awaited()
            mock_reset.assert_not_awaited()
            mock_comments.assert_not_awaited()
            mock_queue.enqueue.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_enqueue_when_batch_already_pending(self):
        with (
            patch("demetra.services.daemons.listener.get_session_by_pr_link", new_callable=AsyncMock) as mock_db,
            patch(
                "demetra.services.daemons.listener.increment_listener_attempts", new_callable=AsyncMock, return_value=1
            ),
            patch("demetra.services.daemons.listener.reset_listener_attempts", new_callable=AsyncMock),
            patch("demetra.services.daemons.listener.get_coderabbit_comments", new_callable=AsyncMock) as mock_comments,
            patch("demetra.services.daemons.listener.save_pending_comments", return_value=False),
            patch("demetra.services.daemons.listener.queue") as mock_queue,
        ):
            mock_db.return_value = self._session()
            mock_comments.return_value = self.COMMENTS
            assert await process_coderabbit_comments_notification(self.PR_INFO) is False
            mock_queue.enqueue.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_false_when_redis_save_fails(self):
        with (
            patch("demetra.services.daemons.listener.get_session_by_pr_link", new_callable=AsyncMock) as mock_db,
            patch(
                "demetra.services.daemons.listener.increment_listener_attempts", new_callable=AsyncMock, return_value=1
            ),
            patch("demetra.services.daemons.listener.get_coderabbit_comments", new_callable=AsyncMock) as mock_comments,
            patch("demetra.services.daemons.listener.save_pending_comments", return_value=None),
            patch("demetra.services.daemons.listener.queue") as mock_queue,
        ):
            mock_db.return_value = self._session()
            mock_comments.return_value = self.COMMENTS
            assert await process_coderabbit_comments_notification(self.PR_INFO) is False
            mock_queue.enqueue.assert_not_called()

    @pytest.mark.asyncio
    async def test_marks_read_without_comments(self):
        with (
            patch("demetra.services.daemons.listener.get_session_by_pr_link", new_callable=AsyncMock) as mock_db,
            patch(
                "demetra.services.daemons.listener.increment_listener_attempts", new_callable=AsyncMock, return_value=1
            ),
            patch("demetra.services.daemons.listener.reset_listener_attempts", new_callable=AsyncMock) as mock_reset,
            patch("demetra.services.daemons.listener.get_coderabbit_comments", new_callable=AsyncMock, return_value=[]),
            patch("demetra.services.daemons.listener.queue") as mock_queue,
        ):
            mock_db.return_value = self._session()
            assert await process_coderabbit_comments_notification(self.PR_INFO) is True
            mock_queue.enqueue.assert_not_called()
            mock_reset.assert_awaited_once_with("TASK-123")

    @pytest.mark.asyncio
    async def test_marks_read_when_attempts_exceeded(self):
        with (
            patch("demetra.services.daemons.listener.get_session_by_pr_link", new_callable=AsyncMock) as mock_db,
            patch(
                "demetra.services.daemons.listener.increment_listener_attempts", new_callable=AsyncMock, return_value=6
            ),
            patch("demetra.services.daemons.listener.get_coderabbit_comments", new_callable=AsyncMock) as mock_comments,
            patch("demetra.services.daemons.listener.queue") as mock_queue,
        ):
            mock_db.return_value = self._session()
            assert await process_coderabbit_comments_notification(self.PR_INFO) is True
            mock_comments.assert_not_awaited()
            mock_queue.enqueue.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_false_when_fetch_fails(self):
        with (
            patch("demetra.services.daemons.listener.get_session_by_pr_link", new_callable=AsyncMock) as mock_db,
            patch(
                "demetra.services.daemons.listener.increment_listener_attempts", new_callable=AsyncMock, return_value=1
            ),
            patch(
                "demetra.services.daemons.listener.get_coderabbit_comments",
                new_callable=AsyncMock,
                side_effect=RuntimeError("gh failed"),
            ),
            patch("demetra.services.daemons.listener.queue") as mock_queue,
        ):
            mock_db.return_value = self._session()
            assert await process_coderabbit_comments_notification(self.PR_INFO) is False
            mock_queue.enqueue.assert_not_called()


class TestListenerEntrypoint:
    @pytest.mark.asyncio
    async def test_main_poll_interval_exists(self):
        from demetra.settings import LISTENER_POLL_INTERVAL

        assert LISTENER_POLL_INTERVAL == 60

    @pytest.mark.asyncio
    async def test_main_loop_processes_merge(self):
        notifications = [
            {
                "id": "1",
                "reason": "mention",
                "subject": {
                    "type": "PullRequest",
                    "title": "PR Title",
                    "url": "https://api.github.com/repos/owner/repo/pulls/42",
                    "latest_comment_url": "https://api.github.com/repos/owner/repo/issues/comments/1",
                },
                "repository": {
                    "full_name": "owner/repo",
                    "clone_url": "https://github.com/owner/repo.git",
                },
            }
        ]

        with (
            patch("demetra.listener.get_notifications", new_callable=AsyncMock) as mock_get,
            patch("demetra.listener.fetch_subject_comment", new_callable=AsyncMock) as mock_body,
            patch("demetra.listener.extract_pr_info") as mock_pr,
            patch("demetra.listener.mentions_demetra_ai_and_merge", return_value=True),
            patch("demetra.listener.mentions_demetra_ai_and_rebase", return_value=False),
            patch("demetra.listener.process_merge_notification", new_callable=AsyncMock) as mock_process,
            patch("demetra.listener.mark_notification_read", new_callable=AsyncMock) as mock_mark_read,
            patch("demetra.listener.init_db", new_callable=AsyncMock),
            patch("demetra.listener.asyncio.sleep", new_callable=AsyncMock, side_effect=StopIteration),
        ):
            mock_get.return_value = notifications
            mock_body.return_value = {"body": "@demetra-ai please merge", "author": "manti-by", "id": "1"}
            mock_process.return_value = True
            mock_pr.return_value = {
                "pr_number": 42,
                "full_name": "owner/repo",
                "title": "PR Title",
                "clone_url": "https://github.com/owner/repo.git",
            }

            from demetra.listener import main

            with pytest.raises(RuntimeError, match="coroutine raised StopIteration"):
                await main()

            mock_process.assert_awaited_once()
            mock_mark_read.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_main_loop_processes_rebase(self):
        notifications = [
            {
                "id": "1",
                "reason": "mention",
                "subject": {
                    "type": "PullRequest",
                    "title": "PR Title",
                    "url": "https://api.github.com/repos/owner/repo/pulls/42",
                    "latest_comment_url": "https://api.github.com/repos/owner/repo/issues/comments/1",
                },
                "repository": {
                    "full_name": "owner/repo",
                    "clone_url": "https://github.com/owner/repo.git",
                },
            }
        ]

        with (
            patch("demetra.listener.get_notifications", new_callable=AsyncMock) as mock_get,
            patch("demetra.listener.fetch_subject_comment", new_callable=AsyncMock) as mock_body,
            patch("demetra.listener.extract_pr_info") as mock_pr,
            patch("demetra.listener.mentions_demetra_ai_and_merge", return_value=False),
            patch("demetra.listener.mentions_demetra_ai_and_rebase", return_value=True),
            patch("demetra.listener.process_rebase_notification", new_callable=AsyncMock) as mock_process,
            patch("demetra.listener.mark_notification_read", new_callable=AsyncMock) as mock_mark_read,
            patch("demetra.listener.init_db", new_callable=AsyncMock),
            patch("demetra.listener.asyncio.sleep", new_callable=AsyncMock, side_effect=StopIteration),
        ):
            mock_get.return_value = notifications
            mock_body.return_value = {"body": "@demetra-ai please rebase", "author": "manti-by", "id": "1"}
            mock_process.return_value = True
            mock_pr.return_value = {
                "pr_number": 42,
                "full_name": "owner/repo",
                "title": "PR Title",
                "clone_url": "https://github.com/owner/repo.git",
            }

            from demetra.listener import main

            with pytest.raises(RuntimeError, match="coroutine raised StopIteration"):
                await main()

            mock_process.assert_awaited_once()
            mock_mark_read.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_main_loop_does_not_mark_read_when_merge_fails(self):
        notifications = [
            {
                "id": "1",
                "reason": "mention",
                "subject": {
                    "type": "PullRequest",
                    "title": "PR Title",
                    "url": "https://api.github.com/repos/owner/repo/pulls/42",
                    "latest_comment_url": "https://api.github.com/repos/owner/repo/issues/comments/1",
                },
                "repository": {
                    "full_name": "owner/repo",
                    "clone_url": "https://github.com/owner/repo.git",
                },
            }
        ]

        with (
            patch("demetra.listener.get_notifications", new_callable=AsyncMock) as mock_get,
            patch("demetra.listener.fetch_subject_comment", new_callable=AsyncMock) as mock_body,
            patch("demetra.listener.extract_pr_info") as mock_pr,
            patch("demetra.listener.mentions_demetra_ai_and_merge", return_value=True),
            patch("demetra.listener.mentions_demetra_ai_and_rebase", return_value=False),
            patch("demetra.listener.process_merge_notification", new_callable=AsyncMock) as mock_process,
            patch("demetra.listener.mark_notification_read", new_callable=AsyncMock) as mock_mark_read,
            patch("demetra.listener.init_db", new_callable=AsyncMock),
            patch("demetra.listener.asyncio.sleep", new_callable=AsyncMock, side_effect=StopIteration),
        ):
            mock_get.return_value = notifications
            mock_body.return_value = {"body": "@demetra-ai please merge", "author": "manti-by", "id": "1"}
            mock_process.return_value = False
            mock_pr.return_value = {
                "pr_number": 42,
                "full_name": "owner/repo",
                "title": "PR Title",
                "clone_url": "https://github.com/owner/repo.git",
            }

            from demetra.listener import main

            with pytest.raises(RuntimeError, match="coroutine raised StopIteration"):
                await main()

            mock_process.assert_awaited_once()
            mock_mark_read.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_main_loop_processes_coderabbit_comments(self):
        notifications = [
            {
                "id": "1",
                "reason": "subscribed",
                "subject": {
                    "type": "PullRequest",
                    "title": "PR Title",
                    "url": "https://api.github.com/repos/owner/repo/pulls/42",
                    "latest_comment_url": "https://api.github.com/repos/owner/repo/issues/comments/1",
                },
                "repository": {"full_name": "owner/repo"},
            }
        ]
        with (
            patch("demetra.listener.get_notifications", new_callable=AsyncMock, return_value=notifications),
            patch(
                "demetra.listener.fetch_subject_comment",
                new_callable=AsyncMock,
                return_value={"body": "a finding in a.py", "author": "coderabbitai[bot]", "id": "1"},
            ),
            patch(
                "demetra.listener.extract_pr_info",
                return_value={"pr_number": 42, "full_name": "owner/repo", "title": "PR Title"},
            ),
            patch("demetra.listener.is_coderabbit_author", return_value=True),
            patch(
                "demetra.listener.process_coderabbit_comments_notification",
                new_callable=AsyncMock,
                return_value=True,
            ) as mock_process,
            patch("demetra.listener.mark_notification_read", new_callable=AsyncMock) as mock_mark_read,
            patch("demetra.listener.init_db", new_callable=AsyncMock),
            patch("demetra.listener.asyncio.sleep", new_callable=AsyncMock, side_effect=StopIteration),
        ):
            from demetra.listener import main

            with pytest.raises(RuntimeError, match="coroutine raised StopIteration"):
                await main()

            mock_process.assert_awaited_once_with(
                pr_info={"pr_number": 42, "full_name": "owner/repo", "title": "PR Title"}
            )
            mock_mark_read.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_main_loop_keeps_coderabbit_notification_unread_when_batch_pending(self):
        notifications = [
            {
                "id": "1",
                "reason": "subscribed",
                "subject": {
                    "type": "PullRequest",
                    "title": "PR Title",
                    "url": "https://api.github.com/repos/owner/repo/pulls/42",
                    "latest_comment_url": "https://api.github.com/repos/owner/repo/issues/comments/1",
                },
                "repository": {"full_name": "owner/repo"},
            }
        ]
        with (
            patch("demetra.listener.get_notifications", new_callable=AsyncMock, return_value=notifications),
            patch(
                "demetra.listener.fetch_subject_comment",
                new_callable=AsyncMock,
                return_value={"body": "a finding in a.py", "author": "coderabbitai[bot]", "id": "1"},
            ),
            patch(
                "demetra.listener.extract_pr_info",
                return_value={"pr_number": 42, "full_name": "owner/repo", "title": "PR Title"},
            ),
            patch("demetra.listener.is_coderabbit_author", return_value=True),
            patch(
                "demetra.listener.process_coderabbit_comments_notification",
                new_callable=AsyncMock,
                return_value=False,
            ) as mock_process,
            patch("demetra.listener.mark_notification_read", new_callable=AsyncMock) as mock_mark_read,
            patch("demetra.listener.init_db", new_callable=AsyncMock),
            patch("demetra.listener.asyncio.sleep", new_callable=AsyncMock, side_effect=StopIteration),
        ):
            from demetra.listener import main

            with pytest.raises(RuntimeError, match="coroutine raised StopIteration"):
                await main()

            mock_process.assert_awaited_once()
            mock_mark_read.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_main_loop_does_not_mark_read_when_rebase_fails(self):
        notifications = [
            {
                "id": "1",
                "reason": "mention",
                "subject": {
                    "type": "PullRequest",
                    "title": "PR Title",
                    "url": "https://api.github.com/repos/owner/repo/pulls/42",
                    "latest_comment_url": "https://api.github.com/repos/owner/repo/issues/comments/1",
                },
                "repository": {
                    "full_name": "owner/repo",
                    "clone_url": "https://github.com/owner/repo.git",
                },
            }
        ]

        with (
            patch("demetra.listener.get_notifications", new_callable=AsyncMock) as mock_get,
            patch("demetra.listener.fetch_subject_comment", new_callable=AsyncMock) as mock_body,
            patch("demetra.listener.extract_pr_info") as mock_pr,
            patch("demetra.listener.mentions_demetra_ai_and_merge", return_value=False),
            patch("demetra.listener.mentions_demetra_ai_and_rebase", return_value=True),
            patch("demetra.listener.process_rebase_notification", new_callable=AsyncMock) as mock_process,
            patch("demetra.listener.mark_notification_read", new_callable=AsyncMock) as mock_mark_read,
            patch("demetra.listener.init_db", new_callable=AsyncMock),
            patch("demetra.listener.asyncio.sleep", new_callable=AsyncMock, side_effect=StopIteration),
        ):
            mock_get.return_value = notifications
            mock_body.return_value = {"body": "@demetra-ai please rebase", "author": "manti-by", "id": "1"}
            mock_process.return_value = False
            mock_pr.return_value = {
                "pr_number": 42,
                "full_name": "owner/repo",
                "title": "PR Title",
                "clone_url": "https://github.com/owner/repo.git",
            }

            from demetra.listener import main

            with pytest.raises(RuntimeError, match="coroutine raised StopIteration"):
                await main()

            mock_process.assert_awaited_once()
            mock_mark_read.assert_not_awaited()
