import asyncio
from collections.abc import AsyncGenerator
from contextlib import ExitStack, contextmanager
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from faker import Faker
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession

from demetra.app import app
from demetra.library.models import LinearTask, UserResponse
from demetra.library.tables import metadata
from demetra.library.tables import sessions as sessions_table
from demetra.services import database as _database_module
from demetra.services.auth import create_jwt_token
from demetra.services.database import _engine_cache, get_async_engine, get_async_session_maker
from demetra.settings import DB_HOST, DB_PASSWORD, DB_PORT, DB_USER


fake = Faker()

_test_db_engine = None


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_db_engine():
    global _test_db_engine
    if _test_db_engine is None:
        _test_db_engine = get_async_engine(db_name="test_demetra")
    return _test_db_engine


@pytest_asyncio.fixture(scope="session")
async def setup_test_db(test_db_engine):
    _engine_cache.clear()
    admin_engine = get_async_engine(db_name="postgres")
    async with AsyncSession(admin_engine) as connection:
        await connection.execute(
            text(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'test_demetra' AND pid <> pg_backend_pid()"
            )
        )
        await connection.execute(text("DROP DATABASE IF EXISTS test_demetra"))
        await connection.execute(text("CREATE DATABASE test_demetra"))
    await admin_engine.dispose()

    sync_url = f"postgresql+psycopg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/test_demetra"
    sync_engine = create_engine(sync_url)
    metadata.create_all(sync_engine)
    sync_engine.dispose()

    _original_db_name = _database_module.DB_NAME
    _database_module.DB_NAME = "test_demetra"

    yield

    _database_module.DB_NAME = _original_db_name
    if _test_db_engine is not None:
        await _test_db_engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_connection(test_db_engine, setup_test_db):
    async_session_maker = get_async_session_maker(test_db_engine)

    async with async_session_maker() as session:
        async with session.begin():
            yield session
            await session.rollback()


@pytest_asyncio.fixture(scope="function", autouse=True)
async def cleanup_db_connections(test_db_engine):
    yield
    async with test_db_engine.begin() as conn:
        await conn.execute(sessions_table.delete())
    await test_db_engine.dispose()
    _engine_cache.clear()


@pytest.fixture
def faker():
    return fake


@pytest.fixture
def linear_team_id() -> str:
    return f"team-{uuid4().hex[:8]}"


@pytest.fixture
def linear_state_id() -> str:
    return f"state-{uuid4().hex[:8]}"


@pytest.fixture
def linear_issue_id() -> str:
    return f"issue-{uuid4().hex[:8]}"


@pytest.fixture
def linear_identifier() -> str:
    return f"MNT-{fake.random_int(min=1, max=999)}"


@pytest.fixture
def linear_graphql_response_success(linear_issue_id: str, linear_identifier: str) -> dict:
    return {
        "data": {
            "issueCreate": {
                "success": True,
                "issue": {
                    "id": linear_issue_id,
                    "identifier": linear_identifier,
                    "title": fake.sentence(nb_words=4),
                },
            }
        }
    }


@pytest.fixture
def linear_graphql_response_failure() -> dict:
    return {
        "data": {
            "issueCreate": {
                "success": False,
            }
        }
    }


@pytest.fixture
def groq_processed_data() -> dict:
    return {
        "title": fake.sentence(nb_words=4),
        "description": fake.paragraph(nb_sentences=3),
        "technical_requirements": fake.paragraph(nb_sentences=2),
        "acceptance_criteria": fake.paragraph(nb_sentences=2),
        "project_name": "demetra",
    }


@pytest.fixture
def linear_ticket_data(linear_issue_id: str, linear_identifier: str) -> dict:
    return {
        "ticket_id": linear_issue_id,
        "identifier": linear_identifier,
        "title": fake.sentence(nb_words=4),
    }


@pytest.fixture
async def mock_graphql_request(
    linear_graphql_response_success: dict,
) -> AsyncGenerator[AsyncMock]:
    with patch(
        "demetra.services.linear.graphql_request",
        new_callable=AsyncMock,
    ) as mock:
        mock.return_value = linear_graphql_response_success
        yield mock


@pytest.fixture
async def mock_groq(groq_processed_data: dict) -> AsyncGenerator[AsyncMock]:
    with patch(
        "demetra.api.tickets.process_text_with_groq",
        new_callable=AsyncMock,
    ) as mock:
        mock.return_value = groq_processed_data
        yield mock


@pytest.fixture
async def mock_create_linear_ticket(
    linear_ticket_data: dict,
) -> AsyncGenerator[AsyncMock]:
    with patch(
        "demetra.api.tickets.create_linear_ticket",
        new_callable=AsyncMock,
    ) as mock:
        mock.return_value = linear_ticket_data
        yield mock


@pytest.fixture
def linear_settings(linear_team_id: str, linear_state_id: str):
    return {
        "team_id": linear_team_id,
        "states": {
            "todo": linear_state_id,
        },
    }


@pytest.fixture
async def mock_linear_settings(linear_settings: dict):
    with patch("demetra.services.linear.LINEAR", linear_settings):
        yield


@pytest.fixture
def linear_task_data() -> dict:
    return {
        "id": f"issue-{uuid4().hex[:8]}",
        "identifier": f"MNT-{fake.random_int(min=1, max=999)}",
        "title": fake.sentence(nb_words=4),
        "description": fake.paragraph(nb_sentences=2),
        "priority": fake.random_int(min=1, max=4),
        "createdAt": fake.date_time().isoformat(),
        "branchName": f"feature/{fake.slug()}",
        "project": {"name": fake.word()},
        "state": {"name": "todo"},
        "comments": {"nodes": []},
    }


@pytest.fixture
def linear_task_data_demetra(linear_task_data: dict) -> dict:
    linear_task_data.update({"project": {"name": "demetra"}})
    return linear_task_data


@pytest.fixture
def linear_task_data_with_comments(linear_task_data_demetra: dict) -> dict:
    linear_task_data_demetra.update(
        {
            "comments": {
                "nodes": [
                    {"body": "First question from the team?"},
                    {"body": "Second question about the implementation?"},
                ]
            }
        }
    )
    return linear_task_data_demetra


@pytest.fixture
def graphql_todo_issues_response_with_comments(linear_task_data_with_comments: dict) -> dict:
    return {"data": {"issues": {"nodes": [linear_task_data_with_comments]}}}


@pytest.fixture
def linear_task(linear_task_data: dict):
    return LinearTask(
        id=linear_task_data["id"],
        identifier=linear_task_data["identifier"],
        title=linear_task_data["title"],
        description=linear_task_data["description"],
        priority=linear_task_data["priority"],
        created_at=linear_task_data["createdAt"],
        project_name=linear_task_data["project"]["name"],
    )


@pytest.fixture
def graphql_todo_issues_response(linear_task_data: dict) -> dict:
    return {"data": {"issues": {"nodes": [linear_task_data]}}}


@pytest.fixture
def graphql_todo_issues_response_demetra(linear_task_data_demetra: dict) -> dict:
    return {"data": {"issues": {"nodes": [linear_task_data_demetra]}}}


@pytest.fixture
def graphql_todo_issues_multiple_response() -> dict:
    tasks = []
    for _ in range(2):
        tasks.append(
            {
                "id": f"issue-{uuid4().hex[:8]}",
                "identifier": f"MNT-{fake.random_int(min=1, max=999)}",
                "title": fake.sentence(nb_words=4),
                "description": fake.paragraph(nb_sentences=2),
                "priority": fake.random_int(min=1, max=4),
                "createdAt": fake.date_time().isoformat(),
                "branchName": f"feature/{fake.slug()}",
                "project": {"name": fake.word()},
                "state": {"name": "todo"},
                "comments": {"nodes": []},
            }
        )
    return {"data": {"issues": {"nodes": tasks}}}


@pytest.fixture
def graphql_todo_issues_multiple_response_demetra() -> dict:
    tasks = []
    for _ in range(2):
        tasks.append(
            {
                "id": f"issue-{uuid4().hex[:8]}",
                "identifier": f"MNT-{fake.random_int(min=1, max=999)}",
                "title": fake.sentence(nb_words=4),
                "description": fake.paragraph(nb_sentences=2),
                "priority": fake.random_int(min=1, max=4),
                "createdAt": fake.date_time().isoformat(),
                "branchName": f"feature/{fake.slug()}",
                "project": {"name": "demetra"},
                "state": {"name": "todo"},
                "comments": {"nodes": []},
            }
        )
    return {"data": {"issues": {"nodes": tasks}}}


@pytest.fixture
def graphql_empty_response() -> dict:
    return {"data": {"issues": {"nodes": []}}}


@pytest.fixture
def graphql_update_success_response() -> dict:
    return {
        "data": {
            "issueUpdate": {
                "success": True,
                "issue": {
                    "id": f"issue-{uuid4().hex[:8]}",
                    "state": {"id": f"state-{uuid4().hex[:8]}", "name": fake.word()},
                },
            }
        }
    }


@pytest.fixture
def mock_linked_projects():
    return {"demetra": (str(uuid4()), str(uuid4()))}


@pytest.fixture
def graphql_update_failure_response() -> dict:
    return {
        "data": {
            "issueUpdate": {
                "success": False,
            }
        }
    }


@pytest.fixture
def graphql_comment_success_response() -> dict:
    return {
        "data": {
            "commentCreate": {
                "success": True,
                "comment": {
                    "id": f"comment-{uuid4().hex[:8]}",
                    "body": fake.sentence(),
                },
            }
        }
    }


@pytest.fixture
def graphql_comment_failure_response() -> dict:
    return {
        "data": {
            "commentCreate": {
                "success": False,
            }
        }
    }


@pytest.fixture
def db_task_id() -> str:
    return f"TASK-{fake.random_int(min=100, max=999)}"


@pytest.fixture
def db_session_id() -> str:
    return f"session-{uuid4().hex[:8]}"


@pytest.fixture
def db_build_plan() -> str:
    return fake.text(max_nb_chars=100)


@pytest.fixture
def mock_user() -> UserResponse:
    return UserResponse(
        id="test_user_id",
        github_username="testuser",
        email="test@example.com",
        role="admin",
    )


@pytest.fixture
def auth_cookie() -> dict:
    with patch(
        "demetra.services.auth.JWT",
        {
            "secret_key": "test_secret_key",
            "algorithm": "HS256",
            "expiration_days": 14,
        },
    ):
        with patch(
            "demetra.services.auth.get_jwt_token",
            new_callable=AsyncMock,
            return_value={
                "token": "test_token",
                "user_id": "test_user_id",
                "expires_at": "2099-01-01T00:00:00+00:00",
            },
        ):
            token, _ = create_jwt_token("test_user_id")
            return {"auth_token": token}


@contextmanager
def patch_get_current_user(user: UserResponse):
    with ExitStack() as stack:
        patches = [
            patch("demetra.api.tickets.get_current_user", new_callable=AsyncMock),
            patch("demetra.api.projects.get_current_user", new_callable=AsyncMock),
            patch("demetra.api.users.get_current_user", new_callable=AsyncMock),
            patch("demetra.api.github.get_current_user", new_callable=AsyncMock),
            patch("demetra.api.watcher.get_current_user", new_callable=AsyncMock),
            patch("demetra.api.sessions.get_current_user", new_callable=AsyncMock),
        ]
        for p in patches:
            mock = stack.enter_context(p)
            mock.return_value = user
        yield


@pytest.fixture
def authenticated_client(mock_user: UserResponse, auth_cookie: dict):
    with patch_get_current_user(mock_user):
        client = TestClient(app, raise_server_exceptions=False)
        client.cookies = auth_cookie
        yield client


@pytest.fixture
def authenticated_client_no_exception(mock_user: UserResponse, auth_cookie: dict):
    with patch_get_current_user(mock_user):
        client = TestClient(app, raise_server_exceptions=True)
        client.cookies = auth_cookie
        yield client
