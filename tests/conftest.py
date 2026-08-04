import asyncio
from collections.abc import AsyncGenerator
from contextlib import ExitStack, contextmanager
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import bcrypt
import pytest
import pytest_asyncio
from faker import Faker
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession

from demetra.app import app
from demetra.library.models import LinearTask, UserResponse
from demetra.library.tables import metadata
from demetra.services import database as _database_module
from demetra.services.auth import create_jwt_token
from demetra.services.database import (
    _engine_cache,
    create_user,
    get_async_engine,
    get_async_session_maker,
    get_user_by_id,
    upsert_pending_session,
)
from demetra.services.database import (
    get_connection as _get_connection,
)
from demetra.settings import DB_HOST, DB_PASSWORD, DB_PORT, DB_USER


fake = Faker()

_test_db_engine = None


@pytest.fixture(scope="session", autouse=True)
def fast_bcrypt():
    original_gensalt = bcrypt.gensalt
    with patch.object(bcrypt, "gensalt", new=lambda: original_gensalt(rounds=4)):
        yield


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


@pytest.fixture
def faker():
    return fake


@pytest.fixture
def allowlist_seeded(monkeypatch):
    """Enable the allowlist gate for a single test.

    ``IS_ALLOWLIST_ENABLED`` is read per-call by
    :func:`demetra.services.allowlist.is_allowlist_enabled`, so a
    ``monkeypatch.setenv`` here is enough to turn enforcement on without
    reloading the settings module. Opt-in by requesting this fixture; the
    default leave the gate off so existing tests are unaffected.
    """
    monkeypatch.setenv("IS_ALLOWLIST_ENABLED", "true")
    yield


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
def create_test_user():
    async def _create(github_username="testuser", role="admin"):
        user_id = await create_user(
            github_id=f"git-{uuid4().hex[:8]}",
            github_username=github_username,
            email=f"{github_username}@example.com",
        )
        async with _get_connection() as conn:
            await conn.execute(text("UPDATE users SET role = :role WHERE id = :id"), {"role": role, "id": user_id})
            await conn.commit()
        user_data = await get_user_by_id(user_id)
        assert user_data is not None, f"User {user_id} not found after creation"
        return UserResponse(
            id=user_data["id"],
            github_username=user_data["github_username"],
            email=user_data["email"],
            role=user_data["role"],
        )

    return _create


@pytest.fixture
def create_test_session():
    async def _create(task_id="task-123", user_id=None, step="initial"):
        await upsert_pending_session(
            task_id=task_id, session_id=f"sess-{uuid4().hex[:8]}", user_id=user_id, name="Test Session"
        )
        if step != "initial":
            async with _get_connection() as conn:
                await conn.execute(
                    text("UPDATE sessions SET step = :step WHERE task_id = :task_id"),
                    {"step": step, "task_id": task_id},
                )
                await conn.commit()

    return _create


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
        "demetra.services.groq.process_text_with_groq",
        new_callable=AsyncMock,
    ) as mock:
        mock.return_value = groq_processed_data
        yield mock


@pytest.fixture
async def mock_create_linear_ticket(
    linear_ticket_data: dict,
) -> AsyncGenerator[AsyncMock]:
    with patch(
        "demetra.services.linear.create_linear_ticket",
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
    identifier = f"MNT-{fake.random_int(min=1, max=999)}"
    return {
        "id": f"issue-{uuid4().hex[:8]}",
        "identifier": identifier,
        "url": f"https://linear.app/manti-by/issue/{identifier}",
        "title": fake.sentence(nb_words=4),
        "description": fake.paragraph(nb_sentences=2),
        "priority": fake.random_int(min=1, max=4),
        "createdAt": fake.date_time().isoformat(),
        "branchName": f"feature/{fake.slug()}",
        "project": {"name": fake.word()},
        "state": {"name": "todo"},
        "comments": {"nodes": []},
        "labels": {"nodes": []},
    }


@pytest.fixture
def linear_task_data_with_labels(linear_task_data_demetra: dict) -> dict:
    linear_task_data_demetra.update(
        {
            "labels": {
                "nodes": [
                    {"id": "label-1", "name": "bug"},
                    {"id": "label-2", "name": "frontend"},
                ]
            }
        }
    )
    return linear_task_data_demetra


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
                    {
                        "body": "First question from the team?",
                        "resolvedAt": None,
                        "createdAt": "2026-01-01T00:00:00Z",
                        "user": {"name": "Test User"},
                        "children": {
                            "edges": [
                                {
                                    "node": {
                                        "id": "reply-1",
                                        "body": "Answer to first question",
                                        "createdAt": "2026-01-01T01:00:00Z",
                                        "user": {"name": "Another User"},
                                    }
                                }
                            ]
                        },
                    },
                    {
                        "body": "Second question about the implementation?",
                        "resolvedAt": None,
                        "createdAt": "2026-01-02T00:00:00Z",
                        "user": {"name": "Test User"},
                        "children": {"edges": []},
                    },
                ]
            }
        }
    )
    return linear_task_data_demetra


@pytest.fixture
def graphql_todo_issues_response_with_comments(linear_task_data_with_comments: dict) -> dict:
    return {"data": {"issues": {"nodes": [linear_task_data_with_comments]}}}


@pytest.fixture
def graphql_todo_issues_response_with_labels(linear_task_data_with_labels: dict) -> dict:
    return {"data": {"issues": {"nodes": [linear_task_data_with_labels]}}}


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
        labels=[n["name"] for n in linear_task_data.get("labels", {}).get("nodes", []) if n.get("name")],
        url=linear_task_data["url"],
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
                "labels": {"nodes": []},
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
                "labels": {"nodes": []},
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
def linear_full_settings(linear_team_id: str, linear_state_id: str) -> dict:
    return {
        "team_id": linear_team_id,
        "default_state": linear_state_id,
        "default_project": "project-123",
        "feature_label_id": "label-123",
        "states": {"todo": linear_state_id, "in_review": "state-review"},
        "projects": {},
        "api_url": "",
        "client_id": None,
        "client_secret": None,
        "oauth_scope": "",
        "oauth_token_url": "",
        "service_name": "",
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
def graphql_create_ticket_success_response(linear_issue_id: str, linear_identifier: str) -> dict:
    return {
        "data": {
            "issueCreate": {
                "success": True,
                "issue": {
                    "id": linear_issue_id,
                    "identifier": linear_identifier,
                    "title": "Test ticket",
                },
            }
        }
    }


@pytest.fixture
def graphql_create_ticket_failure_response() -> dict:
    return {
        "data": {
            "issueCreate": {
                "success": False,
            }
        }
    }


@pytest.fixture
def graphql_create_ticket_no_issue_response() -> dict:
    return {
        "data": {
            "issueCreate": {
                "success": True,
            }
        }
    }


@pytest.fixture
def graphql_get_issue_by_id_response(linear_task_data_demetra: dict) -> dict:
    return {"data": {"issue": linear_task_data_demetra}}


@pytest.fixture
def graphql_get_issue_by_id_response_with_labels(linear_task_data_with_labels: dict) -> dict:
    return {"data": {"issue": linear_task_data_with_labels}}


@pytest.fixture
def graphql_get_issue_by_id_response_with_comments(linear_task_data_with_comments: dict) -> dict:
    return {"data": {"issue": linear_task_data_with_comments}}


@pytest.fixture
def graphql_get_issue_by_id_not_found_response() -> dict:
    return {"data": {"issue": None}}


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
def jwt_settings() -> dict:
    return {
        "secret_key": "test_secret_key",
        "algorithm": "HS256",
        "expiration_days": 14,
    }


@pytest.fixture
def github_oauth_settings() -> dict:
    return {
        "client_id": "test_client_id",
        "client_secret": "test_client_secret",
        "redirect_uri": "https://example.com/callback",
        "oauth_url": "https://github.com/login/oauth/authorize",
        "token_url": "https://github.com/login/oauth/access_token",
        "user_url": "https://api.github.com/user",
    }


@pytest.fixture
def github_settings(github_oauth_settings: dict) -> dict:
    return {
        "path": "/usr/bin/gh",
        "oauth": github_oauth_settings,
        "webhook": {"secret": None},
        "token": None,
    }


@pytest.fixture
def mock_jwt_settings(jwt_settings: dict):
    with patch("demetra.services.auth.JWT", jwt_settings):
        yield


@pytest.fixture
def mock_github_oauth_settings(github_settings: dict):
    with patch("demetra.services.auth.GITHUB", github_settings):
        yield


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
            patch("demetra.services.auth.get_current_user", new_callable=AsyncMock),
            patch("demetra.api.watcher.get_current_user", new_callable=AsyncMock),
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
def cross_user_client(mock_user: UserResponse, auth_cookie: dict):
    other_user = UserResponse(
        id="other_user_id",
        github_username="otheruser",
        email="other@example.com",
        role="user",
    )
    with patch_get_current_user(other_user):
        client = TestClient(app, raise_server_exceptions=False)
        client.cookies = auth_cookie
        yield client


@pytest.fixture
def authenticated_client_no_exception(mock_user: UserResponse, auth_cookie: dict):
    with patch_get_current_user(mock_user):
        client = TestClient(app, raise_server_exceptions=True)
        client.cookies = auth_cookie
        yield client
