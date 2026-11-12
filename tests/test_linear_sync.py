from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.exc import SQLAlchemyError

from demetra.library.exceptions import LinearError
from demetra.services.linear.graphql import get_query
from demetra.services.linear.mirror import (
    extract_comment_rows,
    extract_comment_threads,
    fetch_complete_issue,
    fetch_issue_comments,
    fetch_linear_project_id,
    fetch_project_issues,
    record_linear_comment,
    store_linear_issue,
)
from demetra.services.linear.sync import sync_linear_mirror
from demetra.services.persistence.database import (
    create_project,
    create_user,
    delete_project,
    get_linear_task,
    list_messages,
)


def _issue(issue_id: str | None = None) -> dict:
    """Build a Linear issue payload.

    Args:
        issue_id: The Linear issue id.

    Returns:
        dict: The issue payload.
    """
    return {
        "id": issue_id or f"issue-{uuid4().hex[:8]}",
        "identifier": "MNT-1",
        "title": "Unify the task model",
        "description": "body",
        "priority": 2,
        "createdAt": "2026-11-01T10:00:00.000Z",
        "updatedAt": "2026-11-02T10:00:00.000Z",
        "branchName": "feature/mnt-1",
        "url": "https://linear.app/mnt/issue/MNT-1",
        "state": {"id": "state-1", "name": "Todo"},
        "project": {"id": "linear-proj-1", "name": "demetra"},
        "labels": {"nodes": [{"id": "l1", "name": "Backend"}]},
        "comments": {"nodes": []},
    }


def _comment(
    comment_id: str, body: str, *, resolved: bool = False, created_at: str = "2026-11-01T11:00:00.000Z"
) -> dict:
    """Build a Linear comment node.

    Args:
        comment_id: The Linear comment id.
        body: The comment body.
        resolved: Whether the comment is resolved.
        created_at: The creation timestamp of the comment.

    Returns:
        dict: The comment node.
    """
    return {
        "id": comment_id,
        "body": body,
        "createdAt": created_at,
        "resolvedAt": "2026-11-01T12:00:00.000Z" if resolved else None,
        "user": {"id": "u1", "name": "Ada"},
        "children": {"edges": []},
    }


class TestExtractCommentThreads:
    def test_extracts_top_level_comments_and_replies(self):
        issue = _issue()
        issue["comments"]["nodes"] = [
            {
                **_comment("c1", "First question"),
                "children": {
                    "edges": [{"node": _comment("c2", "First answer", created_at="2026-11-01T11:05:00.000Z")}]
                },
            }
        ]

        comments = extract_comment_threads(issue)

        assert [comment["id"] for comment in comments] == ["c1", "c2"]
        assert comments[1]["parent_id"] == "c1"
        assert comments[0]["author_name"] == "Ada"

    def test_returns_an_empty_list_without_comments(self):
        assert extract_comment_threads(_issue()) == []

    def test_extract_comment_rows_counts_the_replies(self):
        comments = [
            {
                **_comment("c1", "First question"),
                "children": {"edges": [{"node": _comment("c2", "First answer")}]},
            }
        ]

        rows = extract_comment_rows(comments)

        assert [row["id"] for row in rows] == ["c1", "c2"]
        assert rows[1]["parent_id"] == "c1"

    def test_extract_comment_rows_skips_rows_without_an_id(self):
        comments = [{**_comment("c1", "First question"), "id": None}]

        assert extract_comment_rows(comments) == []


class TestStoreLinearIssue:
    @pytest.mark.asyncio
    async def test_mirrors_the_issue_and_its_comments(self):
        issue = _issue()
        issue["comments"]["nodes"] = [
            {
                **_comment("c1", "First question"),
                "children": {
                    "edges": [{"node": _comment("c2", "First answer", created_at="2026-11-01T11:05:00.000Z")}]
                },
            }
        ]

        task = await store_linear_issue(issue=issue)

        assert task.identifier == "MNT-1"
        assert task.tags == ["Backend"]
        assert task.linear_issue_id == issue["id"]
        assert task.linear_state_name == "Todo"

        messages = await list_messages(task.id)
        assert [message.body for message in messages] == ["First question", "First answer"]
        assert all(message.source == "linear" for message in messages)
        assert messages[1].parent_id == messages[0].id

    @pytest.mark.asyncio
    async def test_is_idempotent(self):
        issue = _issue()
        issue["comments"]["nodes"] = [_comment("c1", "First question")]

        await store_linear_issue(issue=issue)
        await store_linear_issue(issue=issue)

        assert len(await list_messages(issue["id"])) == 1

        mirrored = await get_linear_task(issue["id"])
        assert mirrored is not None
        assert mirrored.title == "Unify the task model"


class TestPagination:
    @pytest.mark.asyncio
    async def test_the_project_query_includes_archived_issues(self):
        query = await get_query(name="get_project_issues")

        assert "includeArchived: true" in query
        assert "after: $after" in query
        assert "filter: {project: {id: {eq: $projectId}}}" in query

    @pytest.mark.asyncio
    async def test_follows_the_issue_cursor(self):
        pages = [
            {
                "data": {
                    "issues": {
                        "nodes": [_issue("issue-1")],
                        "pageInfo": {"hasNextPage": True, "endCursor": "cursor-1"},
                    }
                }
            },
            {
                "data": {
                    "issues": {
                        "nodes": [_issue("issue-2")],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    }
                }
            },
        ]

        with patch("demetra.services.linear.mirror.graphql_request", new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = pages
            issues = await fetch_project_issues("linear-proj-1")

        assert [issue["id"] for issue in issues] == ["issue-1", "issue-2"]
        assert mock_request.await_args_list[1].kwargs["variables"]["after"] == "cursor-1"

    @pytest.mark.asyncio
    async def test_follows_the_comment_cursor(self):
        pages = [
            {
                "data": {
                    "issue": {
                        "comments": {
                            "nodes": [_comment("c1", "first")],
                            "pageInfo": {"hasNextPage": True, "endCursor": "cursor-1"},
                        }
                    }
                }
            },
            {
                "data": {
                    "issue": {
                        "comments": {
                            "nodes": [_comment("c2", "second")],
                            "pageInfo": {"hasNextPage": False, "endCursor": None},
                        }
                    }
                }
            },
        ]

        with patch("demetra.services.linear.mirror.graphql_request", new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = pages
            comments = await fetch_issue_comments("issue-1")

        assert [comment["id"] for comment in comments] == ["c1", "c2"]

    @pytest.mark.asyncio
    async def test_follows_the_reply_cursor_of_a_comment(self):
        first_page = {
            "data": {
                "issue": {
                    "comments": {
                        "nodes": [
                            {
                                **_comment("c1", "First question"),
                                "children": {
                                    "pageInfo": {"hasNextPage": True, "endCursor": "child-cursor"},
                                    "edges": [{"node": _comment("c2", "First answer")}],
                                },
                            }
                        ],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    }
                }
            }
        }
        reply_page = {
            "data": {
                "comment": {
                    "id": "c1",
                    "children": {
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                        "edges": [{"node": _comment("c3", "Late answer")}],
                    },
                }
            }
        }

        with patch("demetra.services.linear.mirror.graphql_request", new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = [first_page, reply_page]
            comments = await fetch_issue_comments("issue-1")

        assert mock_request.await_args_list[1].kwargs["variables"] == {"commentId": "c1", "after": "child-cursor"}
        assert [edge["node"]["id"] for edge in comments[0]["children"]["edges"]] == ["c2", "c3"]

    @pytest.mark.asyncio
    async def test_does_not_query_replies_when_one_page_is_enough(self):
        page = {
            "data": {
                "issue": {
                    "comments": {
                        "nodes": [
                            {
                                **_comment("c1", "First question"),
                                "children": {
                                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                                    "edges": [{"node": _comment("c2", "First answer")}],
                                },
                            }
                        ],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    }
                }
            }
        }

        with patch("demetra.services.linear.mirror.graphql_request", new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = [page]
            comments = await fetch_issue_comments("issue-1")

        assert mock_request.await_count == 1
        assert [edge["node"]["id"] for edge in comments[0]["children"]["edges"]] == ["c2"]

    @pytest.mark.asyncio
    async def test_raises_on_a_graphql_error(self):
        with patch("demetra.services.linear.mirror.graphql_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"errors": [{"message": "boom"}]}
            with pytest.raises(RuntimeError):
                await fetch_project_issues("linear-proj-1")

    @pytest.mark.asyncio
    async def test_rejects_a_cursor_that_does_not_advance(self):
        page = {
            "data": {
                "issues": {
                    "nodes": [_issue("issue-1")],
                    "pageInfo": {"hasNextPage": True, "endCursor": "cursor-1"},
                }
            }
        }

        with patch("demetra.services.linear.mirror.graphql_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = page
            with pytest.raises(LinearError):
                await fetch_project_issues("linear-proj-1")

        assert mock_request.await_count == 2

    @pytest.mark.asyncio
    async def test_rejects_a_missing_cursor(self):
        page = {
            "data": {
                "issues": {
                    "nodes": [_issue("issue-1")],
                    "pageInfo": {"hasNextPage": True, "endCursor": None},
                }
            }
        }

        with patch("demetra.services.linear.mirror.graphql_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = page
            with pytest.raises(LinearError):
                await fetch_project_issues("linear-proj-1")

        assert mock_request.await_count == 1

    @pytest.mark.asyncio
    async def test_rejects_a_reply_cursor_that_does_not_advance(self):
        issue_page = {
            "data": {
                "issue": {
                    "comments": {
                        "nodes": [
                            {
                                **_comment("c1", "First question"),
                                "children": {
                                    "pageInfo": {"hasNextPage": True, "endCursor": "child-cursor"},
                                    "edges": [{"node": _comment("c2", "First answer")}],
                                },
                            }
                        ],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    }
                }
            }
        }
        reply_page = {
            "data": {
                "comment": {
                    "id": "c1",
                    "children": {
                        "pageInfo": {"hasNextPage": True, "endCursor": "child-cursor"},
                        "edges": [{"node": _comment("c3", "Late answer")}],
                    },
                }
            }
        }

        with patch("demetra.services.linear.mirror.graphql_request", new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = [issue_page, reply_page]
            with pytest.raises(LinearError):
                await fetch_issue_comments("issue-1")

    @pytest.mark.asyncio
    async def test_rejects_a_comment_cursor_that_does_not_advance(self):
        page = {
            "data": {
                "issue": {
                    "comments": {
                        "nodes": [_comment("c1", "First question")],
                        "pageInfo": {"hasNextPage": True, "endCursor": "cursor-1"},
                    }
                }
            }
        }

        with patch("demetra.services.linear.mirror.graphql_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = page
            with pytest.raises(LinearError):
                await fetch_issue_comments("issue-1")

        assert mock_request.await_count == 2


class TestFetchCompleteIssue:
    @pytest.mark.asyncio
    async def test_merges_the_complete_comment_page(self):
        issue = _issue()
        issue["comments"]["nodes"] = [_comment("c1", "First question")]
        page = {
            "data": {
                "issue": {
                    "comments": {
                        "nodes": [
                            _comment("c1", "First question"),
                            _comment("c2", "Second question"),
                        ],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    }
                }
            }
        }

        with patch("demetra.services.linear.mirror.graphql_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = page
            complete = await fetch_complete_issue(issue=issue)

        assert [comment["id"] for comment in complete["comments"]["nodes"]] == ["c1", "c2"]

    @pytest.mark.asyncio
    async def test_keeps_the_inline_comments_when_the_fetch_fails(self):
        issue = _issue()
        issue["comments"]["nodes"] = [_comment("c1", "First question")]

        with patch("demetra.services.linear.mirror.graphql_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"errors": [{"message": "boom"}]}
            complete = await fetch_complete_issue(issue=issue)

        assert [comment["id"] for comment in complete["comments"]["nodes"]] == ["c1"]


class TestFetchLinearProjectId:
    @pytest.mark.asyncio
    async def test_resolves_the_project_id_by_name(self):
        payload = {"data": {"projects": {"nodes": [{"id": "linear-proj-1", "name": "demetra"}]}}}

        with patch("demetra.services.linear.mirror.graphql_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = payload
            project_id = await fetch_linear_project_id(name="demetra")

        assert project_id == "linear-proj-1"
        assert mock_request.await_args_list[0].kwargs["variables"] == {"name": "demetra"}

    @pytest.mark.asyncio
    async def test_returns_none_without_a_matching_project(self):
        payload = {"data": {"projects": {"nodes": []}}}

        with patch("demetra.services.linear.mirror.graphql_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = payload
            project_id = await fetch_linear_project_id(name="demetra")

        assert project_id is None

    @pytest.mark.asyncio
    async def test_raises_on_a_graphql_error(self):
        with patch("demetra.services.linear.mirror.graphql_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"errors": [{"message": "boom"}]}
            with pytest.raises(RuntimeError):
                await fetch_linear_project_id(name="demetra")


class TestRecordLinearComment:
    @pytest.mark.asyncio
    async def test_swallows_a_storage_failure(self):
        with (
            patch(
                "demetra.services.linear.mirror.upsert_message",
                new_callable=AsyncMock,
                side_effect=SQLAlchemyError("boom"),
            ),
            patch("demetra.services.linear.mirror.COMMENT_STORE_BACKOFF_SECONDS", 0),
        ):
            stored = await record_linear_comment(task_id="task-1", body="A comment", external_id="comment-1")

        assert stored is None

    @pytest.mark.asyncio
    async def test_retries_the_local_write(self):
        task_id = f"task-{uuid4().hex[:8]}"

        with (
            patch(
                "demetra.services.linear.mirror.upsert_message",
                new_callable=AsyncMock,
                side_effect=[SQLAlchemyError("boom"), None],
            ) as mock_upsert,
            patch("demetra.services.linear.mirror.COMMENT_STORE_BACKOFF_SECONDS", 0),
        ):
            await record_linear_comment(task_id=task_id, body="A comment", external_id="comment-1")

        assert mock_upsert.await_count == 2

    @pytest.mark.asyncio
    async def test_stores_the_comment(self):
        task_id = f"task-{uuid4().hex[:8]}"

        stored = await record_linear_comment(task_id=task_id, body="A comment", external_id="comment-1")

        assert stored is not None
        assert stored.external_id == "comment-1"
        assert stored.source == "linear"


class TestSyncLinearMirror:
    @pytest_asyncio.fixture
    async def owner(self) -> str:
        return await create_user(email=f"{uuid4().hex}@example.com", password_hash="x")

    @pytest.fixture(autouse=True)
    def mock_name_lookup(self) -> Generator[AsyncMock]:
        """Resolve the projects that are linked by name only locally.

        The backfill looks up the Linear id of every project without a stored
        one, so the request has to be answered without the Linear API.
        """
        with patch(
            "demetra.services.linear.sync.fetch_linear_project_id",
            new_callable=AsyncMock,
            return_value=None,
        ) as mock_lookup:
            yield mock_lookup

    @pytest_asyncio.fixture
    async def linked_project(self, owner: str) -> AsyncGenerator[dict]:
        project = await create_project(
            user_id=owner,
            name=f"sync-project-{uuid4().hex[:8]}",
            repository_url=f"https://github.com/owner/sync-{uuid4().hex[:8]}",
            repository_owner="owner",
            repository_name="sync-project",
            local_path="/tmp/sync-project",
            linear_project_id=f"linear-proj-{uuid4().hex[:8]}",
            state="active",
        )
        yield project
        # The test database is shared for the session, so the linked project is
        # removed again to keep the sync scoped to the project under test.
        await delete_project(project_id=project["id"], user_id=owner)

    @pytest_asyncio.fixture
    async def name_only_project(self, owner: str) -> AsyncGenerator[dict]:
        project = await create_project(
            user_id=owner,
            name=f"name-only-project-{uuid4().hex[:8]}",
            repository_url=f"https://github.com/owner/name-only-{uuid4().hex[:8]}",
            repository_owner="owner",
            repository_name="name-only-project",
            local_path="/tmp/name-only-project",
            state="active",
        )
        yield project
        await delete_project(project_id=project["id"], user_id=owner)

    @pytest.mark.asyncio
    async def test_mirrors_every_issue_of_the_linked_project(self, linked_project: dict):
        issue = _issue()
        issue["comments"]["nodes"] = [_comment("c1", "First question")]

        with (
            patch("demetra.services.linear.sync.fetch_project_issues", new_callable=AsyncMock) as mock_issues,
            patch("demetra.services.linear.sync.fetch_issue_comments", new_callable=AsyncMock) as mock_comments,
        ):
            mock_issues.return_value = [issue]
            mock_comments.return_value = issue["comments"]["nodes"]
            report = await sync_linear_mirror()

        assert report.projects == 1
        assert report.issues == 1
        assert report.comments == 1
        assert report.failures == []

        mirrored = await get_linear_task(issue["id"])
        assert mirrored is not None
        assert mirrored.identifier == "MNT-1"
        assert mirrored.project_id == linked_project["id"]

    @pytest.mark.asyncio
    async def test_dry_run_writes_nothing(self, linked_project: dict):
        issue = _issue()

        with (
            patch("demetra.services.linear.sync.fetch_project_issues", new_callable=AsyncMock) as mock_issues,
            patch("demetra.services.linear.sync.fetch_issue_comments", new_callable=AsyncMock) as mock_comments,
        ):
            mock_issues.return_value = [issue]
            mock_comments.return_value = []
            report = await sync_linear_mirror(dry_run=True)

        assert report.issues == 1
        assert await get_linear_task(issue["id"]) is None

    @pytest.mark.asyncio
    async def test_reports_a_failed_project(self, linked_project: dict):
        with patch("demetra.services.linear.sync.fetch_project_issues", new_callable=AsyncMock) as mock_issues:
            mock_issues.side_effect = RuntimeError("boom")
            report = await sync_linear_mirror()

        assert report.issues == 0
        assert len(report.failures) == 1

    @pytest.mark.asyncio
    async def test_reports_a_failed_project_of_a_transport_error(self, linked_project: dict):
        with patch("demetra.services.linear.sync.fetch_project_issues", new_callable=AsyncMock) as mock_issues:
            mock_issues.side_effect = LinearError("boom")
            report = await sync_linear_mirror()

        assert report.issues == 0
        assert len(report.failures) == 1

    @pytest.mark.asyncio
    async def test_reports_a_failed_issue_of_a_transport_error(self, linked_project: dict):
        issue = _issue()

        with (
            patch("demetra.services.linear.sync.fetch_project_issues", new_callable=AsyncMock) as mock_issues,
            patch("demetra.services.linear.sync.fetch_issue_comments", new_callable=AsyncMock) as mock_comments,
        ):
            mock_issues.return_value = [issue]
            mock_comments.side_effect = LinearError("boom")
            report = await sync_linear_mirror()

        assert report.issues == 0
        assert len(report.failures) == 1

    @pytest.mark.asyncio
    async def test_counts_the_replies_in_the_report(self, linked_project: dict):
        issue = _issue()
        comments = [
            {
                **_comment("c1", "First question"),
                "children": {"edges": [{"node": _comment("c2", "First answer")}]},
            }
        ]

        with (
            patch("demetra.services.linear.sync.fetch_project_issues", new_callable=AsyncMock) as mock_issues,
            patch("demetra.services.linear.sync.fetch_issue_comments", new_callable=AsyncMock) as mock_comments,
        ):
            mock_issues.return_value = [issue]
            mock_comments.return_value = comments
            report = await sync_linear_mirror()

        assert report.comments == 2

    @pytest.mark.asyncio
    async def test_records_a_storage_failure_and_continues(self, linked_project: dict):
        first_issue = _issue()
        second_issue = _issue()

        with (
            patch("demetra.services.linear.sync.fetch_project_issues", new_callable=AsyncMock) as mock_issues,
            patch("demetra.services.linear.sync.fetch_issue_comments", new_callable=AsyncMock) as mock_comments,
            patch("demetra.services.linear.sync.store_linear_issue", new_callable=AsyncMock) as mock_store,
        ):
            mock_issues.return_value = [first_issue, second_issue]
            mock_comments.return_value = []
            mock_store.side_effect = [SQLAlchemyError("boom"), None]
            report = await sync_linear_mirror()

        assert report.issues == 2
        assert mock_store.await_count == 2
        assert len(report.failures) == 1
        assert first_issue["id"] in report.failures[0]

    @pytest.mark.asyncio
    async def test_mirrors_a_project_linked_by_name_only(
        self,
        name_only_project: dict,
        mock_name_lookup: AsyncMock,
    ):
        issue = _issue()
        mock_name_lookup.side_effect = lambda name: (
            "linear-proj-name-only" if name == name_only_project["name"] else None
        )

        with (
            patch("demetra.services.linear.sync.fetch_project_issues", new_callable=AsyncMock) as mock_issues,
            patch("demetra.services.linear.sync.fetch_issue_comments", new_callable=AsyncMock) as mock_comments,
        ):
            mock_issues.return_value = [issue]
            mock_comments.return_value = []
            report = await sync_linear_mirror()

        assert report.issues == 1
        assert report.failures == []

        mirrored = await get_linear_task(issue["id"])
        assert mirrored is not None
        assert mirrored.project_id == name_only_project["id"]

    @pytest.mark.asyncio
    async def test_reports_a_failed_name_lookup(self, name_only_project: dict, mock_name_lookup: AsyncMock):
        mock_name_lookup.side_effect = RuntimeError("boom")

        with patch("demetra.services.linear.sync.fetch_project_issues", new_callable=AsyncMock) as mock_issues:
            mock_issues.return_value = []
            report = await sync_linear_mirror()

        assert report.issues == 0
        assert len(report.failures) == 1
