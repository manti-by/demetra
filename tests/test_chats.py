from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from demetra.library.models import Chat, ChatMessage, ChatMessageKind, Context, LinearTask, Project, Session
from demetra.services.chat import (
    build_chat_task,
    get_chat_task,
    is_chat_task,
    record_chat_message,
    record_chat_status,
    resolve_task_by_id,
)
from demetra.services.persistence.database import (
    chat_task_id,
    create_chat,
    create_project,
    delete_project,
    get_chat,
    get_chat_by_task_id,
    get_connection,
    get_session,
    get_session_state,
    get_sessions,
    list_chat_messages,
    list_chats,
    post_chat_message,
    reset_session_for_resume,
    update_chat,
    update_session_step,
)
from demetra.settings import DATABASE
from demetra.workflows.notifications import notify_message, notify_status
from demetra.workflows.research import is_research_task, run_research_step


TEST_USER_ID = "test_user_id"


def _sync_engine():
    url = (
        f"postgresql+psycopg://{DATABASE['user']}:{DATABASE['password']}"
        f"@{DATABASE['host']}:{DATABASE['port']}/{DATABASE['name']}"
    )
    return create_engine(url)


def _ensure_test_user(engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO users (id, github_id, email, role, created_at)
                VALUES (:id, :github_id, :email, 'admin', :created_at)
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {
                "id": TEST_USER_ID,
                "github_id": "chat-test-github-id",
                "email": "chat-test@example.com",
                "created_at": datetime.now(),
            },
        )


async def _create_project(name: str, state: str = "active") -> dict:
    return await create_project(
        user_id=TEST_USER_ID,
        name=name,
        repository_url=f"https://github.com/owner/{name}",
        repository_owner="owner",
        repository_name=name,
        local_path=f"/tmp/{name}",
        state=state,
    )


@pytest.fixture(autouse=True)
def clean_chat_rows(setup_test_db):
    engine = _sync_engine()
    _ensure_test_user(engine)
    yield
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM sessions WHERE task_id LIKE 'CH-%'"))
        connection.execute(text("DELETE FROM projects WHERE user_id = :user_id"), {"user_id": TEST_USER_ID})
    engine.dispose()


@pytest_asyncio.fixture
async def project() -> dict:
    return await _create_project(name=f"chat-project-{uuid4().hex[:8]}")


@pytest_asyncio.fixture
async def chat(project: dict) -> Chat:
    return await create_chat(
        user_id=TEST_USER_ID,
        project_id=project["id"],
        title="Add authentication",
        description="Implement password login",
        tags=["Backend"],
    )


def _project_model(project: dict) -> Project:
    return Project(
        id=project["id"],
        user_id=TEST_USER_ID,
        linear_project_id=None,
        name=project["name"],
        state=project["state"],
        repository_url=project["repository_url"],
        repository_name=project["repository_name"],
        repository_owner=project["repository_owner"],
        local_path=Path(project["local_path"]),
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
    )


def _chat_context(chat: Chat, project: dict, task: LinearTask | None = None) -> Context:
    return Context(
        project=_project_model(project),
        auto_mode=True,
        linear_task=task or build_chat_task(chat=chat, project_name=project["name"], messages=[]),
        branch_name="feature/chat",
        worktree_path=Path(f"/tmp/{project['name']}"),
        session=None,
        chat=chat,
    )


async def _session_for(task_id: str) -> Session:
    session = await get_session(task_id=task_id)
    assert session is not None
    return session


async def _chat_by_task_id(task_id: str) -> Chat:
    chat = await get_chat_by_task_id(task_id=task_id)
    assert chat is not None
    return chat


class TestChatTaskId:
    def test_mints_ch_prefixed_identifier(self):
        assert chat_task_id(chat_id=12) == "CH-12"


class TestCreateChat:
    @pytest.mark.asyncio
    async def test_creates_pending_session_with_matching_task_id(self, project: dict):
        chat = await create_chat(
            user_id=TEST_USER_ID,
            project_id=project["id"],
            title="Add authentication",
            description="Implement password login",
            tags=["Backend", "Research"],
        )

        assert chat.session_task_id == f"CH-{chat.id}"
        session = await _session_for(task_id=chat.session_task_id)
        assert session.step == "initial"
        assert session.name == f"CH-{chat.id}: Add authentication"
        assert session.user_id == TEST_USER_ID
        assert session.project_id == project["id"]
        assert chat.tags == ["Backend", "Research"]

    @pytest.mark.asyncio
    async def test_consecutive_chats_get_distinct_ids(self, project: dict):
        first = await create_chat(
            user_id=TEST_USER_ID,
            project_id=project["id"],
            title="First",
            description="first description",
        )
        second = await create_chat(
            user_id=TEST_USER_ID,
            project_id=project["id"],
            title="Second",
            description="second description",
        )

        assert first.id != second.id
        assert first.session_task_id != second.session_task_id

    @pytest.mark.asyncio
    async def test_failed_insert_leaves_no_session_row(self):
        with pytest.raises(IntegrityError):
            await create_chat(
                user_id=TEST_USER_ID,
                project_id=str(uuid4()),
                title="Orphan",
                description="project does not exist",
            )

        async with get_connection() as connection:
            result = await connection.execute(text("SELECT count(*) FROM sessions WHERE name LIKE 'CH-%: Orphan'"))
            assert result.scalar_one() == 0


class TestChatQueries:
    @pytest.mark.asyncio
    async def test_get_chat_by_task_id_and_user_scoping(self, chat: Chat):
        assert (await _chat_by_task_id(task_id=chat.session_task_id)).id == chat.id
        scoped = await get_chat(task_id=chat.session_task_id, user_id=TEST_USER_ID)
        assert scoped is not None
        assert scoped.id == chat.id
        assert await get_chat(task_id=chat.session_task_id, user_id="someone_else") is None
        assert await get_chat_by_task_id(task_id="CH-999999") is None

    @pytest.mark.asyncio
    async def test_list_chats_filters_by_tag(self, project: dict):
        await create_chat(
            user_id=TEST_USER_ID,
            project_id=project["id"],
            title="Research one",
            description="desc",
            tags=["Research"],
        )
        await create_chat(
            user_id=TEST_USER_ID,
            project_id=project["id"],
            title="Backend one",
            description="desc",
            tags=["Backend"],
        )

        all_chats = await list_chats(user_id=TEST_USER_ID)
        research_chats = await list_chats(user_id=TEST_USER_ID, tag="Research")

        assert len(all_chats) == 2
        assert [chat.title for chat in research_chats] == ["Research one"]

    @pytest.mark.asyncio
    async def test_update_chat_only_edits_description(self, chat: Chat):
        updated = await update_chat(
            task_id=chat.session_task_id,
            user_id=TEST_USER_ID,
            description="Updated description",
        )

        assert updated is not None
        assert updated.description == "Updated description"
        assert updated.title == chat.title
        assert updated.tags == chat.tags

    @pytest.mark.asyncio
    async def test_update_chat_is_user_scoped(self, chat: Chat):
        assert await update_chat(task_id=chat.session_task_id, user_id="other", description="x") is None

    @pytest.mark.asyncio
    async def test_post_and_list_messages_in_order(self, chat: Chat):
        await post_chat_message(
            task_id=chat.session_task_id,
            body="user question",
            author_id=TEST_USER_ID,
        )
        await post_chat_message(
            task_id=chat.session_task_id,
            body="system answer",
            is_system=True,
            kind="plan",
        )

        messages = await list_chat_messages(task_id=chat.session_task_id)

        assert [message.body for message in messages] == ["user question", "system answer"]
        assert messages[0].is_system is False
        assert messages[1].is_system is True
        assert messages[1].kind == "plan"

    @pytest.mark.asyncio
    async def test_post_message_to_unknown_chat_returns_none(self):
        assert await post_chat_message(task_id="CH-999999", body="hello") is None

    @pytest.mark.asyncio
    async def test_reset_session_for_resume_clears_plan_and_attempts(self, chat: Chat):
        await update_session_step(task_id=chat.session_task_id, step="awaiting_input")

        await reset_session_for_resume(task_id=chat.session_task_id)

        session = await _session_for(task_id=chat.session_task_id)
        assert session.step == "initial"
        assert session.build_plan == ""
        assert session.posted_to_linear is False
        assert session.run_attempts == 0


class TestChatSessionsListing:
    @pytest.mark.asyncio
    async def test_sessions_expose_chat_id_and_tags(self, chat: Chat):
        sessions = await get_sessions(user_id=TEST_USER_ID)

        row = next(session for session in sessions if session["task_id"] == chat.session_task_id)
        assert row["chat_id"] == chat.id
        assert row["tags"] == ["Backend"]

    @pytest.mark.asyncio
    async def test_sessions_tag_filter_excludes_linear_sessions(self, chat: Chat):
        async with get_connection() as connection:
            await connection.execute(
                text(
                    """
                    INSERT INTO sessions (task_id, name, build_plan, posted_to_linear, step,
                        project_id, user_id, run_attempts, listener_attempts, created_at, updated_at)
                    VALUES (:task_id, 'MNT-1: linear', '', false, 'initial', NULL, :user_id, 0, 0, :now, :now)
                    """
                ),
                {"task_id": f"MNT-{uuid4().hex[:6]}", "user_id": TEST_USER_ID, "now": datetime.now()},
            )
            await connection.commit()

        filtered = await get_sessions(user_id=TEST_USER_ID, tag="Backend")
        linear_rows = await get_sessions(user_id=TEST_USER_ID, tag="Nonexistent")

        assert {row["task_id"] for row in filtered} == {chat.session_task_id}
        assert linear_rows == []

    @pytest.mark.asyncio
    async def test_get_session_state_reports_chat_flag(self, chat: Chat):
        state = await get_session_state(task_id=chat.session_task_id, user_id=TEST_USER_ID)

        assert state is not None
        assert state.is_chat is True
        assert state.step == "initial"


class TestBuildChatTask:
    def test_maps_chat_fields_and_filters_thread_context(self):
        chat = Chat(
            id=4,
            session_task_id="CH-4",
            title="Add authentication",
            description="Implement password login",
            user_id=TEST_USER_ID,
            project_id="project-1",
            tags=["Backend"],
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
        )
        messages = [
            _message(kind="message", body="user reply"),
            _message(kind="plan", body="build plan body"),
            _message(kind="question", body="which database?"),
            _message(kind="failure", body="build failed"),
        ]

        task = build_chat_task(chat=chat, project_name="demetra", messages=messages)

        assert task.id == "CH-4"
        assert task.identifier == "CH-4"
        assert task.title == "Add authentication"
        assert task.description == "Implement password login"
        assert task.project_name == "demetra"
        assert task.labels == ["Backend"]
        assert task.comments == ["user reply", "which database?"]

    @pytest.mark.asyncio
    async def test_get_chat_task_resolves_project_name(self, chat: Chat, project: dict):
        await post_chat_message(task_id=chat.session_task_id, body="hello", author_id=TEST_USER_ID)

        resolved = await get_chat_task(task_id=chat.session_task_id)

        assert resolved is not None
        task, resolved_chat = resolved
        assert resolved_chat.id == chat.id
        assert task.project_name == project["name"]
        assert task.comments == ["hello"]

    @pytest.mark.asyncio
    async def test_get_chat_task_returns_none_for_linear_task(self):
        assert await get_chat_task(task_id="MNT-123") is None

    @pytest.mark.asyncio
    async def test_resolve_task_by_id_prefers_chat(self, chat: Chat):
        with patch("demetra.services.chat.tasks.get_linear_task_by_id", new_callable=AsyncMock) as mock_linear:
            task = await resolve_task_by_id(task_id=chat.session_task_id)

        assert task is not None
        assert task.id == chat.session_task_id
        mock_linear.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_resolve_task_by_id_falls_back_to_linear(self):
        linear_task = LinearTask(
            id="linear-id",
            identifier="MNT-123",
            title="Linear task",
            description="desc",
            priority=1,
            created_at=datetime.now().isoformat(),
        )
        with patch(
            "demetra.services.chat.tasks.get_linear_task_by_id",
            new_callable=AsyncMock,
            return_value=linear_task,
        ) as mock_linear:
            task = await resolve_task_by_id(task_id="MNT-123")

        assert task is linear_task
        mock_linear.assert_awaited_once_with(task_id="MNT-123")


class TestChatNotifications:
    @pytest.mark.asyncio
    async def test_is_chat_task(self, chat: Chat):
        assert await is_chat_task(task_id=chat.session_task_id) is True
        assert await is_chat_task(task_id="MNT-123") is False

    @pytest.mark.asyncio
    async def test_record_chat_status_writes_step_backed_states_only(self, chat: Chat):
        await record_chat_status(task_id=chat.session_task_id, state="awaiting_input")
        assert (await _session_for(task_id=chat.session_task_id)).step == "awaiting_input"

        await record_chat_status(task_id=chat.session_task_id, state="in_progress")
        assert (await _session_for(task_id=chat.session_task_id)).step == "awaiting_input"

    @pytest.mark.asyncio
    async def test_record_chat_message_stores_system_message(self, chat: Chat):
        stored = await record_chat_message(task_id=chat.session_task_id, body="failure body", kind="failure")

        assert stored is True
        messages = await list_chat_messages(task_id=chat.session_task_id)
        assert [(message.body, message.kind, message.is_system) for message in messages] == [
            ("failure body", "failure", True)
        ]

    @pytest.mark.asyncio
    async def test_record_chat_message_returns_false_without_chat(self):
        assert await record_chat_message(task_id="CH-999999", body="body") is False


class TestNotificationGate:
    @pytest.mark.asyncio
    async def test_chat_status_never_touches_linear(self, chat: Chat, project: dict):
        context = _chat_context(chat=chat, project=project)

        with (
            patch("demetra.workflows.notifications.update_ticket_status", new_callable=AsyncMock) as mock_update,
            patch("demetra.workflows.notifications.post_comment", new_callable=AsyncMock) as mock_comment,
        ):
            assert await notify_status(context=context, state="awaiting_input") is True
            assert await notify_message(context=context, body="hello", kind="plan") is True

        mock_update.assert_not_awaited()
        mock_comment.assert_not_awaited()
        assert (await _session_for(task_id=chat.session_task_id)).step == "awaiting_input"
        assert [message.body for message in await list_chat_messages(task_id=chat.session_task_id)] == ["hello"]

    @pytest.mark.asyncio
    async def test_linear_status_and_message_still_use_linear(self, project: dict):
        context = Context(
            project=_project_model(project),
            auto_mode=True,
            linear_task=LinearTask(
                id="linear-id",
                identifier="MNT-123",
                title="Linear task",
                description="desc",
                priority=1,
                created_at=datetime.now().isoformat(),
            ),
            branch_name="feature/linear",
            worktree_path=Path("/tmp/linear"),
            session=None,
        )

        with (
            patch("demetra.workflows.notifications.update_ticket_status", new_callable=AsyncMock) as mock_update,
            patch("demetra.workflows.notifications.post_comment", new_callable=AsyncMock) as mock_comment,
            patch("demetra.library.models.SessionEnvironment.linear_state", return_value="state-1"),
        ):
            await notify_status(context=context, state="awaiting_input")
            await notify_message(context=context, body="hello")

        mock_update.assert_awaited_once_with(task_id="linear-id", state_id="state-1")
        mock_comment.assert_awaited_once_with(task_id="linear-id", body="hello")


class TestChatAPI:
    @pytest.mark.asyncio
    async def test_create_returns_201_and_enqueues(self, authenticated_client: TestClient, project: dict):
        with patch("demetra.api.chats.enqueue_workflow") as mock_enqueue:
            response = authenticated_client.post(
                "/api/v1/chats",
                json={
                    "title": "Add authentication",
                    "description": "Implement password login",
                    "project_id": project["id"],
                    "tags": ["Backend", "backend", " "],
                },
            )

        assert response.status_code == 201
        payload = response.json()
        assert payload["session_task_id"] == f"CH-{payload['id']}"
        assert payload["tags"] == ["Backend"]
        mock_enqueue.assert_called_once_with(project_name=project["name"], task_id=payload["session_task_id"])
        assert await get_session(task_id=payload["session_task_id"]) is not None

    @pytest.mark.asyncio
    async def test_create_rejects_empty_title(self, authenticated_client: TestClient, project: dict):
        response = authenticated_client.post(
            "/api/v1/chats",
            json={"title": "   ", "description": "desc", "project_id": project["id"], "tags": []},
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_create_rejects_unknown_project(self, authenticated_client: TestClient):
        response = authenticated_client.post(
            "/api/v1/chats",
            json={"title": "Title", "description": "desc", "project_id": str(uuid4()), "tags": []},
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_create_rejects_unready_project(self, authenticated_client: TestClient):
        pending = await _create_project(name=f"pending-{uuid4().hex[:8]}", state="provisioning")
        response = authenticated_client.post(
            "/api/v1/chats",
            json={"title": "Title", "description": "desc", "project_id": pending["id"], "tags": []},
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_detail_returns_thread_and_session_state(self, authenticated_client: TestClient, chat: Chat):
        await post_chat_message(task_id=chat.session_task_id, body="hello", author_id=TEST_USER_ID)

        response = authenticated_client.get(f"/api/v1/chats/{chat.session_task_id}")

        assert response.status_code == 200
        payload = response.json()
        assert payload["chat"]["id"] == chat.id
        assert [message["body"] for message in payload["messages"]] == ["hello"]
        assert payload["session"]["is_chat"] is True
        assert payload["session"]["step"] == "initial"

    @pytest.mark.asyncio
    async def test_detail_is_user_scoped(self, cross_user_client: TestClient, chat: Chat):
        response = cross_user_client.get(f"/api/v1/chats/{chat.session_task_id}")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_detail_rejects_non_chat_task_ids(self, authenticated_client: TestClient):
        response = authenticated_client.get("/api/v1/chats/not-a-chat")

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_patch_updates_description(self, authenticated_client: TestClient, chat: Chat):
        response = authenticated_client.patch(
            f"/api/v1/chats/{chat.session_task_id}",
            json={"description": "Updated description"},
        )

        assert response.status_code == 200
        assert response.json()["chat"]["description"] == "Updated description"

    @pytest.mark.asyncio
    async def test_patch_rejects_empty_and_invalid_updates(self, authenticated_client: TestClient, chat: Chat):
        empty = authenticated_client.patch(f"/api/v1/chats/{chat.session_task_id}", json={})
        invalid = authenticated_client.patch(
            f"/api/v1/chats/{chat.session_task_id}",
            json={"status": "not-a-status"},
        )

        assert empty.status_code == 400
        assert invalid.status_code == 400

    @pytest.mark.asyncio
    async def test_patch_status_initial_resets_and_requeues(
        self, authenticated_client: TestClient, chat: Chat, project: dict
    ):
        await update_session_step(task_id=chat.session_task_id, step="failed")

        with patch("demetra.api.chats.enqueue_workflow") as mock_enqueue:
            response = authenticated_client.patch(
                f"/api/v1/chats/{chat.session_task_id}",
                json={"status": "initial"},
            )

        assert response.status_code == 200
        assert (await _session_for(task_id=chat.session_task_id)).step == "initial"
        mock_enqueue.assert_called_once_with(project_name=project["name"], task_id=chat.session_task_id)

    @pytest.mark.asyncio
    async def test_patch_status_applies_terminal_step(self, authenticated_client: TestClient, chat: Chat):
        response = authenticated_client.patch(
            f"/api/v1/chats/{chat.session_task_id}",
            json={"status": "completed"},
        )

        assert response.status_code == 200
        assert (await _session_for(task_id=chat.session_task_id)).step == "completed"

    @pytest.mark.asyncio
    async def test_message_resumes_awaiting_input_session(
        self, authenticated_client: TestClient, chat: Chat, project: dict
    ):
        await update_session_step(task_id=chat.session_task_id, step="awaiting_input")

        with patch("demetra.api.chats.enqueue_workflow") as mock_enqueue:
            response = authenticated_client.post(
                f"/api/v1/chats/{chat.session_task_id}/messages",
                json={"body": "use postgres"},
            )

        assert response.status_code == 201
        payload = response.json()
        assert payload["resumed"] is True
        assert payload["message"]["body"] == "use postgres"
        assert payload["message"]["is_system"] is False
        assert (await _session_for(task_id=chat.session_task_id)).step == "initial"
        mock_enqueue.assert_called_once_with(project_name=project["name"], task_id=chat.session_task_id)

    @pytest.mark.asyncio
    async def test_message_does_not_resume_running_session(self, authenticated_client: TestClient, chat: Chat):
        await update_session_step(task_id=chat.session_task_id, step="build")

        with patch("demetra.api.chats.enqueue_workflow") as mock_enqueue:
            response = authenticated_client.post(
                f"/api/v1/chats/{chat.session_task_id}/messages",
                json={"body": "note"},
            )

        assert response.status_code == 201
        assert response.json()["resumed"] is False
        mock_enqueue.assert_not_called()

    @pytest.mark.asyncio
    async def test_message_rejects_empty_body(self, authenticated_client: TestClient, chat: Chat):
        response = authenticated_client.post(
            f"/api/v1/chats/{chat.session_task_id}/messages",
            json={"body": "  "},
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_sessions_endpoint_exposes_chat_metadata(self, authenticated_client: TestClient, chat: Chat):
        response = authenticated_client.get("/api/v1/sessions")

        assert response.status_code == 200
        row = next(session for session in response.json() if session["task_id"] == chat.session_task_id)
        assert row["chat_id"] == chat.id
        assert row["tags"] == ["Backend"]

    @pytest.mark.asyncio
    async def test_sessions_endpoint_filters_by_tag(self, authenticated_client: TestClient, chat: Chat):
        response = authenticated_client.get("/api/v1/sessions", params={"tag": "Backend"})

        assert response.status_code == 200
        assert [row["task_id"] for row in response.json()] == [chat.session_task_id]


class TestDeleteProjectWithChats:
    @pytest.mark.asyncio
    async def test_delete_project_raises_when_chats_exist(self, project: dict, chat: Chat):
        with pytest.raises(ValueError, match="chat"):
            await delete_project(project_id=project["id"], user_id=TEST_USER_ID)

    @pytest.mark.asyncio
    async def test_delete_project_endpoint_returns_409(
        self, authenticated_client: TestClient, project: dict, chat: Chat
    ):
        response = authenticated_client.delete(f"/api/v1/projects/{project['id']}")

        assert response.status_code == 409


class TestChatResearch:
    @pytest.mark.asyncio
    async def test_research_tag_triggers_research_flow(self):
        chat = Chat(
            id=7,
            session_task_id="CH-7",
            title="Investigate caching",
            description="desc",
            user_id=TEST_USER_ID,
            project_id="project-1",
            tags=["Research"],
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
        )
        task = build_chat_task(chat=chat, project_name="demetra", messages=[])

        with patch("demetra.workflows.research.LINEAR", {"research_labels": ["Research"]}):
            assert is_research_task(linear_task=task) is True

    @pytest.mark.asyncio
    async def test_run_research_step_posts_report_to_thread_without_linear(self, chat: Chat, project: dict):
        context = _chat_context(chat=chat, project=project)

        with (
            patch(
                "demetra.workflows.research._run_research_agent",
                new_callable=AsyncMock,
                return_value="## Research Report\nfindings",
            ),
            patch("demetra.workflows.research.create_research_ticket", new_callable=AsyncMock) as mock_ticket,
            patch("demetra.workflows.research.update_ticket_status", new_callable=AsyncMock) as mock_status,
            patch("demetra.workflows.research.create_issue_relation", new_callable=AsyncMock) as mock_relation,
        ):
            report = await run_research_step(context=context)

        assert report == "## Research Report\nfindings"
        mock_ticket.assert_not_awaited()
        mock_status.assert_not_awaited()
        mock_relation.assert_not_awaited()
        messages = await list_chat_messages(task_id=chat.session_task_id)
        assert [(message.kind, message.body) for message in messages] == [("research", "## Research Report\nfindings")]
        assert (await _session_for(task_id=chat.session_task_id)).step == "researched"

    @pytest.mark.asyncio
    async def test_run_research_step_returns_none_without_report(self, chat: Chat, project: dict):
        context = _chat_context(chat=chat, project=project)

        with patch("demetra.workflows.research._run_research_agent", new_callable=AsyncMock, return_value=None):
            report = await run_research_step(context=context)

        assert report is None
        assert await list_chat_messages(task_id=chat.session_task_id) == []


def _message(*, kind: ChatMessageKind, body: str) -> ChatMessage:
    return ChatMessage(
        id=str(uuid4()),
        chat_id=1,
        session_task_id="CH-1",
        body=body,
        created_at=datetime.now().isoformat(),
        kind=kind,
    )
