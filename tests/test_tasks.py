import asyncio
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.exc import IntegrityError

from demetra.library.models import Task
from demetra.services.persistence.database import (
    create_chat,
    create_project,
    create_user,
    delete_session,
    ensure_task,
    get_linear_task,
    get_session,
    get_sessions,
    get_task,
    list_messages,
    post_chat_message,
    post_message,
    upsert_linear_task,
    upsert_message,
    upsert_pending_session,
    upsert_task,
    upsert_task_with_linear,
)


@pytest_asyncio.fixture
async def owner() -> str:
    return await create_user(email=f"{uuid4().hex}@example.com", password_hash="x")


@pytest_asyncio.fixture
async def project(owner: str) -> dict:
    return await create_project(
        user_id=owner,
        name=f"task-project-{uuid4().hex[:8]}",
        repository_url=f"https://github.com/owner/task-project-{uuid4().hex[:8]}",
        repository_owner="owner",
        repository_name="task-project",
        local_path="/tmp/task-project",
        state="active",
    )


class TestEnsureTask:
    @pytest.mark.asyncio
    async def test_creates_the_task_when_missing(self):
        task_id = f"task-{uuid4().hex[:8]}"

        await ensure_task(task_id=task_id, kind="linear", identifier="MNT-1", title="Add auth")

        task = await get_task(task_id)
        assert task is not None
        assert task.kind == "linear"
        assert task.identifier == "MNT-1"
        assert task.title == "Add auth"

    @pytest.mark.asyncio
    async def test_keeps_the_existing_task_untouched(self):
        task_id = f"task-{uuid4().hex[:8]}"
        await ensure_task(task_id=task_id, kind="linear", identifier="MNT-1", title="Add auth")

        await ensure_task(task_id=task_id, kind="chat", identifier="CH-1", title="Other")

        task = await get_task(task_id)
        assert task is not None
        assert task.kind == "linear"
        assert task.title == "Add auth"

    @pytest.mark.asyncio
    async def test_ignores_an_unknown_project(self):
        task_id = f"task-{uuid4().hex[:8]}"

        await ensure_task(task_id=task_id, kind="linear", identifier="MNT-1", project_id=str(uuid4()))

        task = await get_task(task_id)
        assert task is not None
        assert task.project_id is None


class TestUpsertTask:
    @pytest.mark.asyncio
    async def test_writes_the_generic_fields(self, project: dict):
        task_id = f"task-{uuid4().hex[:8]}"

        task = await upsert_task(
            {
                "id": task_id,
                "kind": "linear",
                "identifier": "MNT-42",
                "title": "Unify the task model",
                "description": "body",
                "priority": 2,
                "state": "Todo",
                "url": "https://linear.app/mnt/issue/MNT-42",
                "tags": ["Backend"],
                "project_id": project["id"],
            }
        )

        assert task.identifier == "MNT-42"
        assert task.priority == 2
        assert task.tags == ["Backend"]
        assert task.project_id == project["id"]

        stored = await get_task(task_id)
        assert stored is not None
        assert stored.title == "Unify the task model"

    @pytest.mark.asyncio
    async def test_keeps_untouched_columns(self):
        task_id = f"task-{uuid4().hex[:8]}"
        await upsert_task({"id": task_id, "kind": "linear", "identifier": "MNT-1", "title": "First"})

        await upsert_task({"id": task_id, "kind": "linear", "state": "Done"})

        task = await get_task(task_id)
        assert task is not None
        assert task.title == "First"
        assert task.state == "Done"

    @pytest.mark.asyncio
    async def test_refreshes_the_modification_time(self):
        task_id = f"task-{uuid4().hex[:8]}"
        created = await upsert_task({"id": task_id, "kind": "linear", "identifier": "MNT-1", "title": "First"})
        await asyncio.sleep(0.01)

        updated = await upsert_task({"id": task_id, "kind": "linear", "title": "Second"})

        assert created.created_at is not None
        assert created.updated_at is not None
        assert updated.updated_at is not None
        assert updated.created_at == created.created_at
        assert updated.updated_at > created.updated_at


class TestUpsertTaskWithLinear:
    @pytest.mark.asyncio
    async def test_writes_the_task_and_its_linear_subtype(self):
        task_id = f"task-{uuid4().hex[:8]}"

        task = await upsert_task_with_linear(
            {"id": task_id, "kind": "linear", "identifier": "MNT-1", "title": "Mirrored"},
            {"task_id": task_id, "linear_issue_id": task_id, "linear_identifier": "MNT-1"},
        )

        assert task.identifier == "MNT-1"
        mirrored = await get_linear_task(task_id)
        assert mirrored is not None
        assert mirrored.linear_identifier == "MNT-1"

    @pytest.mark.asyncio
    async def test_rolls_back_the_task_when_the_linear_subtype_fails(self):
        first_id = f"task-{uuid4().hex[:8]}"
        second_id = f"task-{uuid4().hex[:8]}"
        await upsert_task_with_linear(
            {"id": first_id, "kind": "linear", "identifier": "MNT-1", "title": "First"},
            {"task_id": first_id, "linear_issue_id": "issue-1", "linear_identifier": "MNT-1"},
        )

        with pytest.raises(IntegrityError):
            await upsert_task_with_linear(
                {"id": second_id, "kind": "linear", "identifier": "MNT-2", "title": "Second"},
                {"task_id": second_id, "linear_issue_id": "issue-1", "linear_identifier": "MNT-2"},
            )

        assert await get_task(second_id) is None


class TestMessages:
    @pytest.mark.asyncio
    async def test_stores_and_lists_messages_in_order(self):
        task_id = f"task-{uuid4().hex[:8]}"
        await post_message(task_id=task_id, body="first")
        await post_message(task_id=task_id, body="second")

        stored = await list_messages(task_id)

        assert [message.body for message in stored] == ["first", "second"]
        assert all(message.task_id == task_id for message in stored)

    @pytest.mark.asyncio
    async def test_filters_by_source(self):
        task_id = f"task-{uuid4().hex[:8]}"
        await post_message(task_id=task_id, body="chat turn", source="chat")
        await post_message(task_id=task_id, body="linear comment", source="linear", kind="comment")

        chat_messages = await list_messages(task_id, source="chat")
        linear_messages = await list_messages(task_id, source="linear")

        assert [message.body for message in chat_messages] == ["chat turn"]
        assert [message.body for message in linear_messages] == ["linear comment"]

    @pytest.mark.asyncio
    async def test_upsert_is_idempotent_on_the_external_id(self):
        task_id = f"task-{uuid4().hex[:8]}"

        await upsert_message(task_id=task_id, body="first", external_id="comment-1")
        await upsert_message(task_id=task_id, body="updated", external_id="comment-1")

        stored = await list_messages(task_id)

        assert len(stored) == 1
        assert stored[0].body == "updated"
        assert stored[0].external_id == "comment-1"

    @pytest.mark.asyncio
    async def test_creates_the_task_when_it_is_missing(self):
        task_id = f"task-{uuid4().hex[:8]}"

        await post_message(task_id=task_id, body="orphan")

        task = await get_task(task_id)
        assert task is not None
        assert task.kind == "chat"


class TestChatTask:
    @pytest.mark.asyncio
    async def test_creates_a_chat_task_row(self, owner: str, project: dict):
        chat = await create_chat(
            user_id=owner,
            project_id=project["id"],
            title="Chat about auth",
            description="How do I add auth?",
            tags=["Backend"],
        )

        task = await get_task(chat.id)
        assert task is not None
        assert task.kind == "chat"
        assert task.identifier == chat.id
        assert task.title == "Chat about auth"
        assert task.tags == ["Backend"]

    @pytest.mark.asyncio
    async def test_sessions_expose_the_task_kind(self, owner: str, project: dict):
        chat = await create_chat(
            user_id=owner,
            project_id=project["id"],
            title="Chat about auth",
            description="How do I add auth?",
        )

        rows = await get_sessions(user_id=owner)
        row = next(item for item in rows if item["task_id"] == chat.id)

        assert row["kind"] == "chat"
        assert row["chat_id"] == chat.chat_id

    @pytest.mark.asyncio
    async def test_the_tag_filter_only_matches_chat_sessions(self, owner: str, project: dict):
        chat = await create_chat(
            user_id=owner,
            project_id=project["id"],
            title="Chat about auth",
            description="How do I add auth?",
            tags=["Backend"],
        )
        linear_task_id = f"task-{uuid4().hex[:8]}"
        await upsert_task(
            {
                "id": linear_task_id,
                "kind": "linear",
                "identifier": "MNT-1",
                "title": "Linear issue",
                "tags": ["Backend"],
                "project_id": project["id"],
                "user_id": owner,
            }
        )
        await upsert_pending_session(
            task_id=linear_task_id,
            session_id=None,
            project_id=project["id"],
            user_id=owner,
            name="MNT-1: Linear issue",
        )

        rows = await get_sessions(user_id=owner, tag="Backend")

        assert {row["task_id"] for row in rows} == {chat.id}

    @pytest.mark.asyncio
    async def test_deleting_the_session_removes_the_chat_task(self, owner: str, project: dict):
        chat = await create_chat(
            user_id=owner,
            project_id=project["id"],
            title="Chat about auth",
            description="How do I add auth?",
        )
        await post_message(task_id=chat.id, body="a message")

        assert await delete_session(task_id=chat.id, user_id=owner) is True

        assert await get_task(chat.id) is None
        assert await list_messages(chat.id) == []

    @pytest.mark.asyncio
    async def test_appending_to_a_deleted_chat_does_not_recreate_it(self, owner: str, project: dict):
        chat = await create_chat(
            user_id=owner,
            project_id=project["id"],
            title="Chat about auth",
            description="How do I add auth?",
        )
        assert await delete_session(task_id=chat.id, user_id=owner) is True

        assert await post_chat_message(task_id=chat.id, body="hello") is None

        assert await get_task(chat.id) is None

    @pytest.mark.asyncio
    async def test_an_append_never_creates_the_task_it_writes_to(self, owner: str, project: dict):
        chat = await create_chat(
            user_id=owner,
            project_id=project["id"],
            title="Chat about auth",
            description="How do I add auth?",
        )

        with patch("demetra.services.persistence.database.ensure_task", new_callable=AsyncMock) as mock_ensure:
            message = await post_chat_message(task_id=chat.id, body="hello")

        assert message is not None
        mock_ensure.assert_not_awaited()
        assert await get_task(chat.id) is not None

    @pytest.mark.asyncio
    async def test_a_failed_deletion_keeps_the_session_and_the_chat(self, owner: str, project: dict):
        chat = await create_chat(
            user_id=owner,
            project_id=project["id"],
            title="Chat about auth",
            description="How do I add auth?",
        )

        with patch("demetra.services.persistence.database.select", side_effect=RuntimeError("boom")):
            with pytest.raises(RuntimeError):
                await delete_session(task_id=chat.id, user_id=owner)

        assert await get_session(task_id=chat.id) is not None
        assert await get_task(chat.id) is not None


class TestLinearTaskMirror:
    @pytest.mark.asyncio
    async def test_reads_the_mirrored_linear_task(self, project: dict):
        task_id = str(uuid4())
        await upsert_task(
            {
                "id": task_id,
                "kind": "linear",
                "identifier": "MNT-99",
                "title": "Mirrored issue",
                "tags": ["Backend"],
                "project_id": project["id"],
            }
        )
        await upsert_linear_task({"task_id": task_id, "linear_issue_id": task_id, "linear_identifier": "MNT-99"})

        mirrored = await get_linear_task(task_id)

        assert mirrored is not None
        assert mirrored.identifier == "MNT-99"
        assert mirrored.tags == ["Backend"]
        assert mirrored.linear_issue_id == task_id

    @pytest.mark.asyncio
    async def test_returns_none_for_a_chat_task(self, owner: str, project: dict):
        chat = await create_chat(
            user_id=owner,
            project_id=project["id"],
            title="Chat about auth",
            description="How do I add auth?",
        )

        assert await get_linear_task(chat.id) is None


class TestTaskModel:
    def test_task_text_uses_the_message_bodies(self):
        task = Task(
            id="task-1",
            kind="linear",
            identifier="MNT-1",
            title="Add auth",
            description="body",
            messages=[],
        )

        assert task.text == "Add auth\n(body)"
        assert task.full_title == "MNT-1: Add auth"
