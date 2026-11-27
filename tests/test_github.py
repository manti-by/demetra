import inspect
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from demetra.services.vcs.github import (
    _is_pr_authorization,
    clone_repo,
    create_pull_request,
    extract_pr_link,
    get_coderabbit_comments,
    get_pr_info,
    get_unresolved_review_threads,
    react_to_comment,
    resolve_review_threads,
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

    def test_react_to_comment_import(self):
        assert callable(react_to_comment)

    def test_is_pr_authorization_import(self):
        assert callable(_is_pr_authorization)


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

    def test_rejects_host_containing_github_as_substring(self):
        result = extract_pr_link("https://evilgithub.com/owner/repo/pull/1")
        assert result is None

    def test_rejects_github_host_used_as_subdomain(self):
        result = extract_pr_link("https://github.com.attacker.com/owner/repo/pull/1")
        assert result is None


class TestVerifySignature:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.payload = b'{"test": "data"}'

    def test_returns_false_when_no_secret_configured(self):
        with patch("demetra.services.vcs.github.GITHUB", {"webhook": {"secret": None}}):
            assert verify_signature(self.payload, "sha256=abc") is False

    def test_returns_false_when_signature_header_missing(self):
        with patch("demetra.services.vcs.github.GITHUB", {"webhook": {"secret": "mysecret"}}):
            assert verify_signature(self.payload, None) is False

    def test_returns_false_when_signature_has_wrong_prefix(self):
        with patch("demetra.services.vcs.github.GITHUB", {"webhook": {"secret": "mysecret"}}):
            assert verify_signature(self.payload, "md5=abc") is False

    def test_returns_false_when_signature_mismatch(self):
        with patch("demetra.services.vcs.github.GITHUB", {"webhook": {"secret": "mysecret"}}):
            result = verify_signature(self.payload, "sha256=wrongsignature")
            assert result is False

    def test_returns_true_when_signature_matches(self):
        import hmac

        secret = "mysecret"
        expected_digest = hmac.new(key=secret.encode(), msg=self.payload, digestmod="sha256").hexdigest()
        with patch("demetra.services.vcs.github.GITHUB", {"webhook": {"secret": secret}}):
            result = verify_signature(self.payload, f"sha256={expected_digest}")
            assert result is True


class TestIsPrAuthorization:
    @pytest.fixture
    def owner_payload(self):
        return {
            "comment": {
                "author_association": "OWNER",
                "user": {"login": "owner"},
            },
            "repository": {"owner": {"login": "owner"}, "name": "repo"},
        }

    @pytest.fixture
    def member_payload(self):
        return {
            "comment": {
                "author_association": "MEMBER",
                "user": {"login": "member"},
            },
            "repository": {"owner": {"login": "owner"}, "name": "repo"},
        }

    @pytest.fixture
    def collaborator_payload(self):
        return {
            "comment": {
                "author_association": "COLLABORATOR",
                "user": {"login": "collab"},
            },
            "repository": {"owner": {"login": "owner"}, "name": "repo"},
        }

    @pytest.fixture
    def contributor_payload(self):
        return {
            "comment": {
                "author_association": "CONTRIBUTOR",
                "user": {"login": "contributor"},
            },
            "repository": {"owner": {"login": "owner"}, "name": "repo"},
        }

    @pytest.fixture
    def none_payload(self):
        return {
            "comment": {
                "author_association": "NONE",
                "user": {"login": "stranger"},
            },
            "repository": {"owner": {"login": "owner"}, "name": "repo"},
        }

    @pytest.fixture(autouse=True)
    def _setup_github_token(self):
        with patch("demetra.services.vcs.github.GITHUB", {"token": "test_token"}):
            yield

    def _mock_github_api(self, permission: str):
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={"permission": permission})
        mock_get = MagicMock()
        mock_get.return_value.__aenter__.return_value = mock_resp
        return patch("aiohttp.ClientSession.get", mock_get)

    @pytest.mark.asyncio
    async def test_owner_is_authorized(self, owner_payload):
        result = await _is_pr_authorization(owner_payload)
        assert result is True

    @pytest.mark.asyncio
    async def test_member_is_authorized(self, member_payload):
        with self._mock_github_api("write"):
            result = await _is_pr_authorization(member_payload)
            assert result is True

    @pytest.mark.asyncio
    async def test_collaborator_is_authorized(self, collaborator_payload):
        with self._mock_github_api("write"):
            result = await _is_pr_authorization(collaborator_payload)
            assert result is True

    @pytest.mark.asyncio
    async def test_collaborator_with_admin_is_authorized(self, collaborator_payload):
        with self._mock_github_api("admin"):
            result = await _is_pr_authorization(collaborator_payload)
            assert result is True

    @pytest.mark.asyncio
    async def test_contributor_is_not_authorized(self, contributor_payload):
        with self._mock_github_api("read"):
            result = await _is_pr_authorization(contributor_payload)
            assert result is False

    @pytest.mark.asyncio
    async def test_none_is_not_authorized(self, none_payload):
        with self._mock_github_api("none"):
            result = await _is_pr_authorization(none_payload)
            assert result is False

    @pytest.mark.asyncio
    async def test_owner_login_fallback(self):
        payload = {
            "comment": {
                "author_association": "NONE",
                "user": {"login": "owner"},
            },
            "repository": {"owner": {"login": "owner"}},
        }
        result = await _is_pr_authorization(payload)
        assert result is True

    @pytest.mark.asyncio
    async def test_mismatched_owner_login_not_authorized(self):
        payload = {
            "comment": {
                "author_association": "NONE",
                "user": {"login": "notowner"},
            },
            "repository": {"owner": {"login": "owner"}, "name": "repo"},
        }
        with self._mock_github_api("none"):
            result = await _is_pr_authorization(payload)
            assert result is False

    @pytest.mark.asyncio
    async def test_api_error_returns_false(self, collaborator_payload):
        mock_resp = AsyncMock()
        mock_resp.status = 404
        mock_get = MagicMock()
        mock_get.return_value.__aenter__.return_value = mock_resp
        with patch("aiohttp.ClientSession.get", mock_get):
            result = await _is_pr_authorization(collaborator_payload)
            assert result is False

    @pytest.mark.asyncio
    async def test_no_token_returns_false(self, collaborator_payload):
        with patch("demetra.services.vcs.github.GITHUB", {"token": None}):
            result = await _is_pr_authorization(collaborator_payload)
            assert result is False


class TestWebhookRebaseHandler:
    @pytest.fixture(autouse=True)
    def _setup_github_token(self):
        with patch("demetra.services.vcs.github.GITHUB", {"token": "test_token"}):
            yield

    def _mock_github_api(self, permission: str):
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={"permission": permission})
        mock_get = MagicMock()
        mock_get.return_value.__aenter__.return_value = mock_resp
        return patch("aiohttp.ClientSession.get", mock_get)

    @pytest.mark.asyncio
    async def test_ignores_comment_without_demetra_ai(self):
        payload = {
            "comment": {"body": "looks good to me", "author_association": "OWNER", "user": {"login": "owner"}},
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
            "comment": {"body": "please rebase", "author_association": "OWNER", "user": {"login": "owner"}},
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
        assert result == {"action": "ignored", "reason": "unauthorized user"}

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
                "name": "repo",
                "owner": {"login": "owner"},
            },
        }
        with self._mock_github_api("none"):
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
                "name": "repo",
                "owner": {"login": "owner"},
            },
        }
        with (
            self._mock_github_api("write"),
            patch("demetra.services.vcs.github.get_session_by_pr_link", new_callable=AsyncMock) as mock_db,
        ):
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
                "name": "repo",
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
            self._mock_github_api("write"),
            patch("demetra.services.vcs.github.get_session_by_pr_link", new_callable=AsyncMock) as mock_db,
            patch("demetra.services.vcs.github.queue") as mock_queue,
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
            self._mock_github_api("write"),
            patch("demetra.services.vcs.github.get_session_by_pr_link", new_callable=AsyncMock) as mock_db,
            patch("demetra.services.vcs.github.queue") as mock_queue,
        ):
            mock_db.return_value = session
            result = await webhook_rebase_handler(payload)
            assert result == {"action": "enqueued_merge", "pr_number": 42, "repository": "owner/repo"}
            mock_queue.enqueue.assert_called_once()

    @pytest.mark.asyncio
    async def test_reacts_to_triggering_comment_before_enqueue(self):
        payload = self._authorized_comment_payload("@demetra-ai rebase")
        payload["comment"]["id"] = 99
        from demetra.library.models import Session

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
            self._mock_github_api("write"),
            patch("demetra.services.vcs.github.get_session_by_pr_link", new_callable=AsyncMock) as mock_db,
            patch("demetra.services.vcs.github.react_to_comment", new_callable=AsyncMock) as mock_react,
            patch("demetra.services.vcs.github.queue") as mock_queue,
        ):
            mock_db.return_value = session
            result = await webhook_rebase_handler(payload)
            assert result == {"action": "enqueued_rebase", "pr_number": 42, "repository": "owner/repo"}
            mock_react.assert_awaited_once()
            assert mock_react.await_args is not None
            assert mock_react.await_args.kwargs["comment_id"] == "99"
            assert mock_react.await_args.kwargs["full_name"] == "owner/repo"
            mock_queue.enqueue.assert_called_once()

    @pytest.mark.asyncio
    async def test_rejects_unprivileged_user(self):
        payload = {
            "comment": {"body": "please rebase", "author_association": "CONTRIBUTOR", "user": {"login": "contributor"}},
            "issue": {"number": 99, "pull_request": {"url": "https://api.github.com/repo/pulls/99"}},
            "repository": {
                "clone_url": "https://github.com/owner/repo.git",
                "full_name": "owner/repo",
                "name": "repo",
                "owner": {"login": "owner"},
            },
        }
        with self._mock_github_api("read"):
            result = await webhook_rebase_handler(payload)
            assert result == {"action": "ignored", "reason": "unauthorized user"}

    @pytest.mark.asyncio
    async def test_detects_rebase_case_insensitively(self):
        from demetra.library.models import Session

        payload = {
            "comment": {
                "body": "@DEMETRA-AI REBASE",
                "author_association": "COLLABORATOR",
                "user": {"login": "collab"},
            },
            "issue": {"number": 7, "pull_request": {"url": "https://api.github.com/repo/pulls/7"}},
            "repository": {
                "clone_url": "https://github.com/owner/repo.git",
                "full_name": "owner/repo",
                "name": "repo",
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
            self._mock_github_api("write"),
            patch("demetra.services.vcs.github.get_session_by_pr_link", new_callable=AsyncMock) as mock_db,
            patch("demetra.services.vcs.github.queue") as mock_queue,
        ):
            mock_db.return_value = session
            result = await webhook_rebase_handler(payload)
            assert result["action"] == "enqueued_rebase"
            mock_queue.enqueue.assert_called_once()


class TestCreatePullRequest:
    @pytest.mark.asyncio
    async def test_calls_run_command_with_correct_args(self):
        with patch("demetra.services.vcs.github.run_command", new_callable=AsyncMock) as mock_run:
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
                "--assignee",
                "demetra-ai",
                "--reviewer",
                "manti-by",
            ]

    @pytest.mark.asyncio
    async def test_accepts_custom_base_branch(self):
        with patch("demetra.services.vcs.github.run_command", new_callable=AsyncMock) as mock_run:
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
        with patch("demetra.services.vcs.github.run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (
                0,
                '{"headRefName": "feature/test", "baseRefName": "main"}',
                "",
            )
            result = await get_pr_info(pr_number=42, full_name="owner/repo", target_path=Path("/tmp/repo"))
            assert result == ("feature/test", "main")

    @pytest.mark.asyncio
    async def test_raises_on_nonzero_exit(self):
        with patch("demetra.services.vcs.github.run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (1, "", "PR not found")
            result = await get_pr_info(pr_number=999, full_name="owner/repo", target_path=Path("/tmp/repo"))
            assert result is None


class TestReactToComment:
    @pytest.mark.asyncio
    async def test_posts_eyes_reaction_to_issue_comment(self):
        with patch("demetra.services.vcs.github.run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (0, "", "")
            result = await react_to_comment(comment_id="42", full_name="owner/repo", target_path=Path("/tmp/repo"))

        assert result is True
        mock_run.assert_awaited_once()
        assert mock_run.await_args is not None
        command = mock_run.await_args.kwargs["command"]
        assert command[1:] == [
            "api",
            "--method",
            "POST",
            "-f",
            "content=eyes",
            "repos/owner/repo/issues/comments/42/reactions",
        ]
        assert mock_run.await_args.kwargs["disable_stdio"] is True

    @pytest.mark.asyncio
    async def test_returns_false_on_api_failure(self):
        with patch("demetra.services.vcs.github.run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (1, "", "API error")
            result = await react_to_comment(comment_id="42", full_name="owner/repo", target_path=Path("/tmp/repo"))

        assert result is False

    @pytest.mark.asyncio
    async def test_invalid_comment_id_skips_run_command(self):
        with patch("demetra.services.vcs.github.run_command", new_callable=AsyncMock) as mock_run:
            result = await react_to_comment(comment_id="not-a-number", full_name="owner/repo", target_path=Path("/tmp"))

        assert result is False
        mock_run.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_empty_comment_id_skips_run_command(self):
        with patch("demetra.services.vcs.github.run_command", new_callable=AsyncMock) as mock_run:
            result = await react_to_comment(comment_id="", full_name="owner/repo", target_path=Path("/tmp"))

        assert result is False
        mock_run.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_invalid_full_name_skips_run_command(self):
        with patch("demetra.services.vcs.github.run_command", new_callable=AsyncMock) as mock_run:
            result = await react_to_comment(comment_id="42", full_name="owner/repo;bad", target_path=Path("/tmp"))

        assert result is False
        mock_run.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_run_command_error_returns_false(self):
        with patch("demetra.services.vcs.github.run_command", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = OSError("gh not found")
            result = await react_to_comment(comment_id="42", full_name="owner/repo", target_path=Path("/tmp"))

        assert result is False


class TestGetCoderabbitComments:
    THREADS = [
        {
            "id": "THREAD_1",
            "path": "a.py",
            "line": 12,
            "comments": {
                "nodes": [
                    {
                        "id": "COMMENT_1",
                        "body": "  first finding  ",
                        "diffHunk": "@@ -1 +1 @@",
                        "author": {"login": "coderabbitai[bot]"},
                        "line": 12,
                    },
                    {"id": "COMMENT_2", "body": "human reply", "author": {"login": "manti-by"}},
                ]
            },
        },
        {
            "id": "THREAD_2",
            "comments": {"nodes": [{"body": "second finding", "author": {"login": "CodeRabbitAI"}}]},
        },
    ]

    @pytest.mark.asyncio
    async def test_keeps_only_coderabbit_comments_with_thread_ids(self):
        with patch(
            "demetra.services.vcs.github.get_unresolved_review_threads",
            new_callable=AsyncMock,
            return_value=self.THREADS,
        ) as mock_threads:
            result = await get_coderabbit_comments(pr_number=42, full_name="owner/repo", target_path=Path("/tmp/repo"))

        mock_threads.assert_awaited_once_with(
            pr_number=42, full_name="owner/repo", target_path=Path("/tmp/repo"), environment=None, project_id=None
        )
        assert [comment["thread_id"] for comment in result] == ["THREAD_1", "THREAD_2"]
        assert result[0] == {
            "thread_id": "THREAD_1",
            "comment_id": "COMMENT_1",
            "body": "first finding",
            "path": "a.py",
            "line": 12,
            "diff_hunk": "@@ -1 +1 @@",
            "author": "coderabbitai[bot]",
        }
        assert result[1]["thread_id"] == "THREAD_2"

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_coderabbit_comments(self):
        with patch(
            "demetra.services.vcs.github.get_unresolved_review_threads", new_callable=AsyncMock, return_value=[]
        ):
            assert await get_coderabbit_comments(42, "owner/repo", Path("/tmp/repo")) == []

    @pytest.mark.asyncio
    async def test_review_thread_query_includes_node_ids(self):
        with patch("demetra.services.vcs.github.run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (
                1,
                "",
                "boom",
            )
            with pytest.raises(RuntimeError):
                await get_unresolved_review_threads(pr_number=42, full_name="owner/repo", target_path=Path("/tmp/repo"))
            assert mock_run.await_args is not None
            query = mock_run.await_args.kwargs["command"][4]
            assert "nodes{id isResolved" in query
            assert "nodes{id body path diffHunk" in query


class TestResolveReviewThreads:
    @pytest.mark.asyncio
    async def test_resolves_each_thread_and_counts_confirmations(self):
        with patch("demetra.services.vcs.github.run_command", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = [
                (0, '{"data":{"resolveReviewThread":{"thread":{"id":"T1","isResolved":true}}}}', ""),
                (0, '{"data":{"resolveReviewThread":{"thread":{"id":"T2","isResolved":true}}}}', ""),
            ]
            assert await resolve_review_threads(["T1", "T2"], Path("/tmp/repo")) == 2

        assert mock_run.await_count == 2
        assert mock_run.await_args is not None
        command = mock_run.await_args.kwargs["command"]
        assert "mutation($threadId:ID!)" in command[4]
        assert command[-1] == "threadId=T2"

    @pytest.mark.asyncio
    async def test_skips_invalid_ids_and_counts_only_successes(self):
        with patch("demetra.services.vcs.github.run_command", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = [
                (1, "", "not found"),
                (0, '{"data":{"resolveReviewThread":{"thread":{"isResolved":false}}}}', ""),
                (0, "invalid json", ""),
            ]
            assert await resolve_review_threads(["bad id", "T1", "T2", "T3"], Path("/tmp/repo")) == 0
        assert mock_run.await_count == 3

    @pytest.mark.asyncio
    async def test_no_threads_resolves_nothing(self):
        with patch("demetra.services.vcs.github.run_command", new_callable=AsyncMock) as mock_run:
            assert await resolve_review_threads([], Path("/tmp/repo")) == 0
        mock_run.assert_not_awaited()


class TestCloneRepo:
    @pytest.mark.asyncio
    async def test_returns_cloned_dict_on_success(self):
        with patch("demetra.services.vcs.github.run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (0, "", "")
            result = await clone_repo(
                repo_url="https://github.com/owner/repo.git",
                parent_path=Path("/tmp"),
                target_path=Path("/tmp/repo"),
            )
            assert result == {"cloned": True}

    @pytest.mark.asyncio
    async def test_raises_on_failure(self):
        with patch("demetra.services.vcs.github.run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (128, "", "Repository not found")
            with pytest.raises(RuntimeError, match="Failed to clone repository"):
                await clone_repo(
                    repo_url="https://github.com/owner/repo.git",
                    parent_path=Path("/tmp"),
                    target_path=Path("/tmp/repo"),
                )
