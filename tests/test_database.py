from uuid import uuid4

import pytest
from sqlalchemy import insert

from demetra.library.tables import project_environments
from demetra.services.database import (
    create_project,
    create_session,
    get_project_environments,
    get_session,
    mark_session_posted,
    save_session,
    update_session_step,
)
from demetra.services.database import get_connection as _get_connection


class TestDatabaseService:
    @pytest.mark.asyncio
    async def test_create_and_read(
        self,
        db_task_id: str,
        db_session_id: str,
    ):
        record = await create_session(db_task_id, db_session_id)
        assert record.task_id == db_task_id
        assert record.session_id == db_session_id
        assert record.build_plan == ""
        assert record.posted_to_linear is False
        assert record.step == "initial"
        assert record.project_id is None
        assert record.user_id is None

        found = await get_session(db_task_id)
        assert found is not None
        assert found.task_id == db_task_id
        assert found.session_id == db_session_id
        assert found.step == "initial"

    @pytest.mark.asyncio
    async def test_read_nonexistent(self):
        result = await get_session("TICKET-999")
        assert result is None

    @pytest.mark.asyncio
    async def test_save_session_with_build_plan(
        self,
        db_task_id: str,
        db_session_id: str,
        db_build_plan: str,
    ):
        session = await save_session(task_id=db_task_id, session_id=db_session_id, build_plan=db_build_plan)
        assert session.task_id == db_task_id
        assert session.session_id == db_session_id
        assert session.build_plan == db_build_plan
        assert session.posted_to_linear is False
        assert session.step == "plan"

        found = await get_session(db_task_id)
        assert found is not None
        assert found.task_id == db_task_id
        assert found.build_plan == db_build_plan
        assert found.posted_to_linear is False
        assert found.step == "plan"

    @pytest.mark.asyncio
    async def test_save_session_updates_existing(
        self,
        db_task_id: str,
        db_session_id: str,
    ):
        await save_session(task_id=db_task_id, session_id=db_session_id, build_plan="Original plan")
        await save_session(task_id=db_task_id, session_id=f"session-{db_session_id}", build_plan="Updated plan")

        found = await get_session(db_task_id)
        assert found is not None
        assert found.session_id != db_session_id
        assert found.build_plan == "Updated plan"
        assert found.posted_to_linear is False
        assert found.step == "plan"

    @pytest.mark.asyncio
    async def test_save_session_preserves_posted_to_linear(
        self,
        db_task_id: str,
        db_session_id: str,
    ):
        await save_session(task_id=db_task_id, session_id=db_session_id, build_plan="Plan A")
        await mark_session_posted(db_task_id)
        await save_session(task_id=db_task_id, session_id=f"session-{db_session_id}", build_plan="Plan B")

        found = await get_session(db_task_id)
        assert found is not None
        assert found.build_plan == "Plan B"
        assert found.posted_to_linear is True

    @pytest.mark.asyncio
    async def test_mark_session_posted(
        self,
        db_task_id: str,
        db_session_id: str,
    ):
        await save_session(task_id=db_task_id, session_id=db_session_id, build_plan="My build plan")

        found = await get_session(db_task_id)
        assert found is not None
        assert found.posted_to_linear is False

        await mark_session_posted(db_task_id)
        found = await get_session(db_task_id)
        assert found is not None
        assert found.posted_to_linear is True

    @pytest.mark.asyncio
    async def test_update_session_step(
        self,
        db_task_id: str,
        db_session_id: str,
    ):
        await create_session(db_task_id, db_session_id)

        found = await get_session(db_task_id)
        assert found is not None
        assert found.step == "initial"

        await update_session_step(db_task_id, "plan")
        found = await get_session(db_task_id)
        assert found is not None
        assert found.step == "plan"

        await update_session_step(db_task_id, "build")
        found = await get_session(db_task_id)
        assert found is not None
        assert found.step == "build"

        await update_session_step(db_task_id, "completed")
        found = await get_session(db_task_id)
        assert found is not None
        assert found.step == "completed"


class TestProjectEnvironments:
    @pytest.mark.asyncio
    async def test_get_project_environments_returns_empty_dict_when_none(self, setup_test_db):
        result = await get_project_environments("nonexistent-project-id")
        assert result == {}

    @pytest.mark.asyncio
    async def test_get_project_environments_returns_all_records(self, faker, setup_test_db):
        project_id = (
            await create_project(
                user_id="test-user",
                name=faker.unique.word(),
                repository_url="https://github.com/owner/repo",
                repository_owner="owner",
                repository_name="repo",
            )
        )["id"]
        async with _get_connection() as conn:
            await conn.execute(
                insert(project_environments).values(
                    id=str(uuid4()),
                    project_id=project_id,
                    key="API_KEY",
                    value="secret123",
                )
            )
            await conn.execute(
                insert(project_environments).values(
                    id=str(uuid4()),
                    project_id=project_id,
                    key="DB_URL",
                    value="postgres://localhost/mydb",
                )
            )
            await conn.commit()

        result = await get_project_environments(project_id)
        assert result == {"API_KEY": "secret123", "DB_URL": "postgres://localhost/mydb"}

    @pytest.mark.asyncio
    async def test_get_project_environments_isolation_between_projects(self, faker, setup_test_db):
        project_a = (
            await create_project(
                user_id="test-user",
                name=faker.unique.word(),
                repository_url="https://github.com/owner/repo",
                repository_owner="owner",
                repository_name="repo",
            )
        )["id"]
        project_b = (
            await create_project(
                user_id="test-user",
                name=faker.unique.word(),
                repository_url="https://github.com/owner/repo",
                repository_owner="owner",
                repository_name="repo",
            )
        )["id"]
        async with _get_connection() as conn:
            await conn.execute(
                insert(project_environments).values(
                    id=str(uuid4()),
                    project_id=project_a,
                    key="ONLY_A",
                    value="value_a",
                )
            )
            await conn.execute(
                insert(project_environments).values(
                    id=str(uuid4()),
                    project_id=project_b,
                    key="ONLY_B",
                    value="value_b",
                )
            )
            await conn.commit()

        result_a = await get_project_environments(project_a)
        result_b = await get_project_environments(project_b)
        assert result_a == {"ONLY_A": "value_a"}
        assert result_b == {"ONLY_B": "value_b"}
