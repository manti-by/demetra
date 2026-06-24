import inspect
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from demetra.services.github import (
    clone_repo,
    create_pull_request,
    extract_pr_link,
    get_pr_info,
    verify_signature,
    webhook_rebase_handler,
)


class TestGitHubModuleImports:
    def test_create_pull_request_import(self):
        assert callable(create_pull_request)

    def test_extract_pr_link_import(self):
        assert callable(extract_pr_link)

    def test_verify_signature_import(self):
        assert callable(verify_signature)

    def test_get_pr_info_import(self):
        assert callable(get_pr_info)

    def test_clone_repo_import(self):
        assert callable(clone_repo)

    def test_webhook_rebase_handler_import(self):
        assert callable(webhook_rebase_handler)


class TestCreatePullRequestFunction:
    def test_create_pull_request_accepts_required_parameters(self):
        sig = inspect.signature(create_pull_request)
        params = list(sig.parameters.keys())

        assert "target_path" in params
        assert "branch_name" in params
        assert "title" in params


class TestExtractPrLink:
    def test_extracts_url_from_stdout(self):
        stdout = "https://github.com/owner/repo/pull/42\n"
        result = extract_pr_link(stdout)
        assert result == "https://github.com/owner/repo/pull/42"

    def test_returns_none_when_no_url(self):
        result = extract_pr_link("Pull request created successfully\n")
        assert result is None

    def test_returns_first_match_when_multiple_urls(self):
        stdout = "https://github.com/owner/repo/pull/1\nsome output\nhttps://github.com/owner/repo/pull/2\n"
        result = extract_pr_link(stdout)
        assert result == "https://github.com/owner/repo/pull/1"

    def test_handles_empty_string(self):
        result = extract_pr_link("")
        assert result is None

    def test_handles_url_without_newline(self):
        result = extract_pr_link("https://github.com/owner/repo/pull/123")
        assert result == "https://github.com/owner/repo/pull/123"


class TestVerifySignature:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.payload = b'{"test": "data"}'

    def test_returns_true_when_no_secret_configured(self):
        with patch("demetra.services.github.GITHUB", {"webhook": {"secret": None}}):
            assert verify_signature(self.payload, "sha256=abc") is True

    def test_returns_false_when_signature_header_missing(self):
        with patch("demetra.services.github.GITHUB", {"webhook": {"secret": "mysecret"}}):
            assert verify_signature(self.payload, None) is False

    def test_returns_false_when_signature_has_wrong_prefix(self):
        with patch("demetra.services.github.GITHUB", {"webhook": {"secret": "mysecret"}}):
            assert verify_signature(self.payload, "md5=abc") is False

    def test_returns_false_when_signature_mismatch(self):
        with patch("demetra.services.github.GITHUB", {"webhook": {"secret": "mysecret"}}):
            result = verify_signature(self.payload, "sha256=wrongsignature")
            assert result is False

    def test_returns_true_when_signature_matches(self):
        import hmac

        secret = "mysecret"
        expected_digest = hmac.new(key=secret.encode(), msg=self.payload, digestmod="sha256").hexdigest()
        with patch("demetra.services.github.GITHUB", {"webhook": {"secret": secret}}):
            result = verify_signature(self.payload, f"sha256={expected_digest}")
            assert result is True


class TestWebhookRebaseHandler:
    @pytest.mark.asyncio
    async def test_ignores_comment_without_demetra_ai(self):
        payload = {
            "comment": {
                "body": "looks good to me",
                "author_association": "COLLABORATOR",
                "user": {"login": "collab"},
            },
            "issue": {"number": 1, "pull_request": {"url": "https://api.github.com/repo/pulls/1"}},
            "repository": {
                "clone_url": "https://github.com/owner/repo.git",
                "full_name": "owner/repo",
                "owner": {"login": "owner"},
            },
        }
        result = await webhook_rebase_handler(payload)
        assert result == {"action": "ignored", "reason": "no recognized command"}

    @pytest.mark.asyncio
    async def test_ignores_non_pr_comment(self):
        payload = {
            "comment": {
                "body": "@demetra-ai rebase",
                "author_association": "COLLABORATOR",
                "user": {"login": "collab"},
            },
            "issue": {"number": 1},
            "repository": {
                "clone_url": "https://github.com/owner/repo.git",
                "full_name": "owner/repo",
                "owner": {"login": "owner"},
            },
        }
        result = await webhook_rebase_handler(payload)
        assert result == {"action": "ignored", "reason": "not a PR comment"}

    @pytest.mark.asyncio
    async def test_ignores_when_missing_repo_info(self):
        payload = {
            "comment": {
                "body": "@demetra-ai rebase",
                "author_association": "COLLABORATOR",
                "user": {"login": "collab"},
            },
            "issue": {"number": 1, "pull_request": {"url": "https://api.github.com/repo/pulls/1"}},
            "repository": {},
        }
        result = await webhook_rebase_handler(payload)
        assert result == {"action": "ignored", "reason": "missing repo info or PR number"}

    @pytest.mark.asyncio
    async def test_ignores_unauthorized_user(self):
        payload = {
            "comment": {
                "body": "@demetra-ai rebase",
                "author_association": "NONE",
                "user": {"login": "stranger"},
            },
            "issue": {"number": 42, "pull_request": {"url": "https://api.github.com/repo/pulls/42"}},
            "repository": {
                "clone_url": "https://github.com/owner/repo.git",
                "full_name": "owner/repo",
                "owner": {"login": "owner"},
            },
        }
        result = await webhook_rebase_handler(payload)
        assert result == {"action": "ignored", "reason": "unauthorized user"}

    @pytest.mark.asyncio
    async def test_ignores_when_no_session_found(self):
        payload = {
            "comment": {
                "body": "@demetra-ai rebase",
                "author_association": "COLLABORATOR",
                "user": {"login": "collab"},
            },
            "issue": {"number": 42, "pull_request": {"url": "https://api.github.com/repo/pulls/42"}},
            "repository": {
                "clone_url": "https://github.com/owner/repo.git",
                "full_name": "owner/repo",
                "owner": {"login": "owner"},
            },
        }
        with patch("demetra.services.github.get_session_by_pr_link", new_callable=AsyncMock) as mock_db:
            mock_db.return_value = None
            result = await webhook_rebase_handler(payload)
            assert result == {"action": "ignored", "reason": "no session found"}

    def _authorized_comment_payload(self, body: str) -> dict:
        return {
            "comment": {
                "body": body,
                "author_association": "COLLABORATOR",
                "user": {"login": "collab"},
            },
            "issue": {"number": 42, "pull_request": {"url": "https://api.github.com/repo/pulls/42"}},
            "repository": {
                "clone_url": "https://github.com/owner/repo.git",
                "full_name": "owner/repo",
                "owner": {"login": "owner"},
            },
        }

    @pytest.mark.asyncio
    async def test_enqueues_rebase_workflow(self):
        from demetra.library.models import Session

        payload = self._authorized_comment_payload("@demetra-ai rebase")
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
            patch("demetra.services.github.get_session_by_pr_link", new_callable=AsyncMock) as mock_db,
            patch("demetra.services.github.queue") as mock_queue,
        ):
            mock_db.return_value = session
            result = await webhook_rebase_handler(payload)
            assert result == {"action": "enqueued_rebase", "pr_number": 42, "repository": "owner/repo"}
            mock_queue.enqueue.assert_called_once()

    @pytest.mark.asyncio
    async def test_enqueues_merge_workflow(self):
        from demetra.library.models import Session

        payload = self._authorized_comment_payload("@demetra-ai merge")
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
            patch("demetra.services.github.get_session_by_pr_link", new_callable=AsyncMock) as mock_db,
            patch("demetra.services.github.queue") as mock_queue,
        ):
            mock_db.return_value = session
            result = await webhook_rebase_handler(payload)
            assert result == {"action": "enqueued_merge", "pr_number": 42, "repository": "owner/repo"}
            mock_queue.enqueue.assert_called_once()

    @pytest.mark.asyncio
    async def test_detects_rebase_case_insensitively(self):
        from demetra.library.models import Session

        payload = {
            "comment": {
                "body": "@DEMETRA-AI REBASE",
                "author_association": "CONTRIBUTOR",
                "user": {"login": "contributor"},
            },
            "issue": {"number": 7, "pull_request": {"url": "https://api.github.com/repo/pulls/7"}},
            "repository": {
                "clone_url": "https://github.com/owner/repo.git",
                "full_name": "owner/repo",
                "owner": {"login": "owner"},
            },
        }
        session = Session(
            task_id="TASK-123",
            build_plan="plan",
            posted_to_linear=True,
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
            pr_link="https://github.com/owner/repo/pull/7",
            project_id="proj-123",
        )
        with (
            patch("demetra.services.github.get_session_by_pr_link", new_callable=AsyncMock) as mock_db,
            patch("demetra.services.github.queue") as mock_queue,
        ):
            mock_db.return_value = session
            result = await webhook_rebase_handler(payload)
            assert result["action"] == "enqueued_rebase"
            mock_queue.enqueue.assert_called_once()


class TestCreatePullRequest:
    @pytest.mark.asyncio
    async def test_calls_run_command_with_correct_args(self):
        with patch("demetra.services.github.run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (0, "https://github.com/owner/repo/pull/1\n", "")
            result = await create_pull_request(
                target_path=Path("/tmp/test"),
                branch_name="feature/test",
                title="Test PR",
            )
            assert result == (0, "https://github.com/owner/repo/pull/1\n", "")
            command = mock_run.call_args[1]["command"]
            assert command[1:] == [
                "pr",
                "create",
                "--title",
                "Test PR",
                "--base",
                "master",
                "--head",
                "feature/test",
            ]

    @pytest.mark.asyncio
    async def test_accepts_custom_base_branch(self):
        with patch("demetra.services.github.run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (0, "", "")
            await create_pull_request(
                target_path=Path("/tmp/test"),
                branch_name="feature/test",
                title="Test PR",
                base="develop",
            )


class TestGetPrInfo:
    @pytest.mark.asyncio
    async def test_returns_parsed_json_on_success(self):
        with patch("demetra.services.github.run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (
                0,
                '{"headRefName": "feature/test", "baseRefName": "main"}',
                "",
            )
            result = await get_pr_info(pr_number=42, full_name="owner/repo", target_path=Path("/tmp/repo"), env={})
            assert result == ("feature/test", "main")

    @pytest.mark.asyncio
    async def test_raises_on_nonzero_exit(self):
        with patch("demetra.services.github.run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (1, "", "PR not found")
            result = await get_pr_info(pr_number=999, full_name="owner/repo", target_path=Path("/tmp/repo"), env={})
            assert result is None


class TestCloneRepo:
    @pytest.mark.asyncio
    async def test_returns_cloned_dict_on_success(self):
        with patch("demetra.services.github.run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (0, "", "")
            result = await clone_repo(
                repo_url="https://github.com/owner/repo.git",
                parent_path=Path("/tmp"),
                target_path=Path("/tmp/repo"),
            )
            assert result == {"cloned": True}

    @pytest.mark.asyncio
    async def test_raises_on_failure(self):
        with patch("demetra.services.github.run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (128, "", "Repository not found")
            with pytest.raises(RuntimeError, match="Failed to clone repository"):
                await clone_repo(
                    repo_url="https://github.com/owner/repo.git",
                    parent_path=Path("/tmp"),
                    target_path=Path("/tmp/repo"),
                )
