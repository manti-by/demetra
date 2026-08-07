import json
from unittest.mock import AsyncMock, patch

import pytest

from demetra.library.models import Session
from demetra.services.daemons.listener import (
    extract_pr_info,
    fetch_subject_body,
    get_notifications,
    mentions_demetra_ai_and_merge,
    mentions_demetra_ai_and_rebase,
    process_merge_notification,
    process_rebase_notification,
    should_process_notification,
)


class TestGetNotifications:
    @pytest.mark.asyncio
    async def test_returns_empty_list_on_api_error(self):
        with patch("demetra.services.daemons.listener.run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (1, "", "API error")
            result = await get_notifications()
            assert result == []

    @pytest.mark.asyncio
    async def test_returns_empty_list_on_empty_response(self):
        with patch("demetra.services.daemons.listener.run_command", new_callable=AsyncMock) as mock_run:
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
        with patch("demetra.services.daemons.listener.run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (0, json.dumps(notifications), "")
            result = await get_notifications()
            assert result == notifications

    @pytest.mark.asyncio
    async def test_handles_invalid_json(self):
        with patch("demetra.services.daemons.listener.run_command", new_callable=AsyncMock) as mock_run:
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
        with patch("demetra.services.daemons.listener.run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (0, "demetra-ai please rebase", "")
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
        with patch("demetra.services.daemons.listener.run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (1, "", "Not found")
            result = await fetch_subject_body(subject)
            assert result == "Title"

    @pytest.mark.asyncio
    async def test_falls_back_to_title_when_body_empty(self):
        subject = {
            "title": "Title",
            "latest_comment_url": "https://api.github.com/repos/owner/repo/issues/comments/123",
        }
        with patch("demetra.services.daemons.listener.run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (0, "", "")
            result = await fetch_subject_body(subject)
            assert result == "Title"


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
            patch("demetra.services.daemons.listener.MAX_LISTENER_ATTEMPTS", 3),
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
            patch("demetra.services.daemons.listener.MAX_LISTENER_ATTEMPTS", 3),
        ):
            mock_db.return_value = session
            mock_inc.return_value = 4

            result = await process_rebase_notification(self.PR_INFO)

            assert result is True
            mock_queue.enqueue.assert_not_called()
            mock_reset.assert_not_awaited()


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
            patch("demetra.listener.fetch_subject_body", new_callable=AsyncMock) as mock_body,
            patch("demetra.listener.extract_pr_info") as mock_pr,
            patch("demetra.listener.mentions_demetra_ai_and_merge", return_value=True),
            patch("demetra.listener.mentions_demetra_ai_and_rebase", return_value=False),
            patch("demetra.listener.process_merge_notification", new_callable=AsyncMock) as mock_process,
            patch("demetra.listener.mark_notification_read", new_callable=AsyncMock) as mock_mark_read,
            patch("demetra.listener.init_db", new_callable=AsyncMock),
            patch("demetra.listener.asyncio.sleep", new_callable=AsyncMock, side_effect=StopIteration),
        ):
            mock_get.return_value = notifications
            mock_body.return_value = "@demetra-ai please merge"
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
            patch("demetra.listener.fetch_subject_body", new_callable=AsyncMock) as mock_body,
            patch("demetra.listener.extract_pr_info") as mock_pr,
            patch("demetra.listener.mentions_demetra_ai_and_merge", return_value=False),
            patch("demetra.listener.mentions_demetra_ai_and_rebase", return_value=True),
            patch("demetra.listener.process_rebase_notification", new_callable=AsyncMock) as mock_process,
            patch("demetra.listener.mark_notification_read", new_callable=AsyncMock) as mock_mark_read,
            patch("demetra.listener.init_db", new_callable=AsyncMock),
            patch("demetra.listener.asyncio.sleep", new_callable=AsyncMock, side_effect=StopIteration),
        ):
            mock_get.return_value = notifications
            mock_body.return_value = "@demetra-ai please rebase"
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
            patch("demetra.listener.fetch_subject_body", new_callable=AsyncMock) as mock_body,
            patch("demetra.listener.extract_pr_info") as mock_pr,
            patch("demetra.listener.mentions_demetra_ai_and_merge", return_value=True),
            patch("demetra.listener.mentions_demetra_ai_and_rebase", return_value=False),
            patch("demetra.listener.process_merge_notification", new_callable=AsyncMock) as mock_process,
            patch("demetra.listener.mark_notification_read", new_callable=AsyncMock) as mock_mark_read,
            patch("demetra.listener.init_db", new_callable=AsyncMock),
            patch("demetra.listener.asyncio.sleep", new_callable=AsyncMock, side_effect=StopIteration),
        ):
            mock_get.return_value = notifications
            mock_body.return_value = "@demetra-ai please merge"
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
            patch("demetra.listener.fetch_subject_body", new_callable=AsyncMock) as mock_body,
            patch("demetra.listener.extract_pr_info") as mock_pr,
            patch("demetra.listener.mentions_demetra_ai_and_merge", return_value=False),
            patch("demetra.listener.mentions_demetra_ai_and_rebase", return_value=True),
            patch("demetra.listener.process_rebase_notification", new_callable=AsyncMock) as mock_process,
            patch("demetra.listener.mark_notification_read", new_callable=AsyncMock) as mock_mark_read,
            patch("demetra.listener.init_db", new_callable=AsyncMock),
            patch("demetra.listener.asyncio.sleep", new_callable=AsyncMock, side_effect=StopIteration),
        ):
            mock_get.return_value = notifications
            mock_body.return_value = "@demetra-ai please rebase"
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
