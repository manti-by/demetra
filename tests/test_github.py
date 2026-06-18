import inspect
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from demetra.services.github import (
    clone_repo,
    create_pull_request,
    extract_pr_link,
    get_pr_info,
    rebase_pr_branch,
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

    def test_rebase_pr_branch_import(self):
        assert callable(rebase_pr_branch)

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
    async def test_ignores_comment_without_rebase_keyword(self):
        payload = {
            "comment": {"body": "looks good to me"},
            "issue": {"number": 1, "pull_request": {"url": "https://api.github.com/repo/pulls/1"}},
            "repository": {"clone_url": "https://github.com/owner/repo.git", "full_name": "owner/repo"},
        }
        result = await webhook_rebase_handler(payload)
        assert result == {"action": "ignored", "reason": "no rebase keyword"}

    @pytest.mark.asyncio
    async def test_ignores_non_pr_comment(self):
        payload = {
            "comment": {"body": "please rebase"},
            "issue": {"number": 1},
            "repository": {"clone_url": "https://github.com/owner/repo.git", "full_name": "owner/repo"},
        }
        result = await webhook_rebase_handler(payload)
        assert result == {"action": "ignored", "reason": "not a PR comment"}

    @pytest.mark.asyncio
    async def test_ignores_when_missing_repo_url(self):
        payload = {
            "comment": {"body": "please rebase"},
            "issue": {"number": 1, "pull_request": {"url": "https://api.github.com/repo/pulls/1"}},
            "repository": {"full_name": "owner/repo"},
        }
        result = await webhook_rebase_handler(payload)
        assert result == {"action": "ignored", "reason": "missing repo URL or PR number"}

    @pytest.mark.asyncio
    async def test_triggers_rebase_on_keyword(self):
        payload = {
            "comment": {"body": "please rebase this PR"},
            "issue": {"number": 42, "pull_request": {"url": "https://api.github.com/repo/pulls/42"}},
            "repository": {
                "clone_url": "https://github.com/owner/repo.git",
                "full_name": "owner/repo",
            },
        }
        with patch(
            "demetra.services.github.rebase_pr_branch",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_rebase:
            result = await webhook_rebase_handler(payload)
            mock_rebase.assert_awaited_once_with(repo_url="https://github.com/owner/repo.git", pr_number=42)
            assert result == {"action": "rebased", "pr_number": 42, "repository": "owner/repo"}

    @pytest.mark.asyncio
    async def test_detects_rebase_case_insensitively(self):
        payload = {
            "comment": {"body": "REBASE please"},
            "issue": {"number": 7, "pull_request": {"url": "https://api.github.com/repo/pulls/7"}},
            "repository": {
                "clone_url": "https://github.com/owner/repo.git",
                "full_name": "owner/repo",
            },
        }
        with patch(
            "demetra.services.github.rebase_pr_branch",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_rebase:
            result = await webhook_rebase_handler(payload)
            mock_rebase.assert_awaited_once()
            assert result["action"] == "rebased"


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
            result = await get_pr_info(repo_path=Path("/tmp/repo"), pr_number=42)
            assert result == {"headRefName": "feature/test", "baseRefName": "main"}

    @pytest.mark.asyncio
    async def test_raises_on_nonzero_exit(self):
        with patch("demetra.services.github.run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (1, "", "PR not found")
            with pytest.raises(RuntimeError, match="Failed to get PR info"):
                await get_pr_info(repo_path=Path("/tmp/repo"), pr_number=999)


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


class TestRebasePrBranch:
    @pytest.mark.asyncio
    async def test_complete_flow_success(self):
        with (
            patch("demetra.services.github.clone_repo", new_callable=AsyncMock) as mock_clone,
            patch("demetra.services.github.get_pr_info", new_callable=AsyncMock) as mock_info,
            patch("demetra.services.github.git_fetch", new_callable=AsyncMock) as mock_fetch,
            patch("demetra.services.github.git_checkout", new_callable=AsyncMock) as mock_checkout,
            patch("demetra.services.github.git_rebase", new_callable=AsyncMock) as mock_rebase,
            patch("demetra.services.github.git_force_push", new_callable=AsyncMock) as mock_push,
        ):
            mock_clone.return_value = {"cloned": True}
            mock_info.return_value = {"headRefName": "feature/test", "baseRefName": "main"}
            mock_rebase.return_value = True

            result = await rebase_pr_branch(
                repo_url="https://github.com/owner/repo.git",
                pr_number=42,
            )

            assert result is True
            mock_clone.assert_awaited_once()
            mock_info.assert_awaited_once()
            mock_fetch.assert_awaited_once()
            mock_checkout.assert_awaited_once_with(
                target_path=mock_checkout.call_args[1]["target_path"],
                branch_name="feature/test",
            )
            mock_rebase.assert_awaited_once()
            mock_push.assert_awaited_once()
