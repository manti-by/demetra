import base64
from unittest.mock import patch
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from sqlalchemy import insert, select

from demetra.library.tables import project_environments
from demetra.services.persistence.database import (
    create_project,
    create_session,
    create_user,
    delete_project,
    delete_project_environment,
    delete_user_environment,
    get_project_environments,
    get_session,
    get_session_history,
    get_session_id_by_task_id,
    get_session_step_name,
    get_user_environments_decrypted,
    increment_listener_attempts,
    increment_run_attempts,
    list_project_environments,
    list_user_environments,
    mark_session_posted,
    record_session_history,
    reset_listener_attempts,
    save_session,
    update_session_linear_link,
    update_session_pr_link,
    update_session_step,
    upsert_pending_session,
    upsert_project_environment,
    upsert_user_environment,
)
from demetra.services.persistence.database import get_connection as _get_connection
from demetra.services.persistence.encryption import decrypt_str


_TEST_SECRET_KEY = "x7uKwdXjK-UPCdQ2DEoUoVoe1sAceCvG9iaJuTbwj20="
_TEST_ENCRYPTION_SALT = "DajyYABtMczCRByZdRh1W"


def _build_test_fernet():
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_TEST_ENCRYPTION_SALT.encode(),
        iterations=480_000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(_TEST_SECRET_KEY.encode()))
    return Fernet(key)


_TEST_FERNET = _build_test_fernet()


class TestDatabaseService:
    @pytest.fixture(autouse=True)
    def _setup_db(self, setup_test_db):
        pass

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

        await update_session_step(db_task_id, "awaiting_input")
        found = await get_session(db_task_id)
        assert found is not None
        assert found.step == "awaiting_input"

    @pytest.mark.asyncio
    async def test_get_session_step_name_returns_step_and_name(
        self,
        db_task_id: str,
        db_session_id: str,
    ):
        await create_session(db_task_id, db_session_id)

        result = await get_session_step_name(db_task_id)
        assert result is not None
        step, name = result
        assert step == "initial"
        assert name == ""

        await update_session_step(db_task_id, "build")
        result = await get_session_step_name(db_task_id)
        assert result is not None
        step, name = result
        assert step == "build"

    @pytest.mark.asyncio
    async def test_get_session_step_name_returns_none_for_missing_task(self):
        result = await get_session_step_name("nonexistent-task")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_session_step_name_scopes_by_user_id(self, db_task_id: str, db_session_id: str):
        await upsert_pending_session(
            task_id=db_task_id,
            session_id=db_session_id,
            user_id="owner-user",
            name="Owner Session",
        )

        result = await get_session_step_name(task_id=db_task_id, user_id="owner-user")
        assert result is not None
        step, name = result
        assert step == "initial"
        assert name == "Owner Session"

        result = await get_session_step_name(task_id=db_task_id, user_id="other-user")
        assert result is None


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


class TestProjectEnvironmentMutations:
    @pytest.mark.asyncio
    async def test_upsert_creates_new_entry(self, faker, setup_test_db):
        project_id = (
            await create_project(
                user_id="test-user",
                name=faker.unique.word(),
                repository_url="https://github.com/owner/repo",
                repository_owner="owner",
                repository_name="repo",
            )
        )["id"]

        entry = await upsert_project_environment(
            project_id=project_id,
            user_id="test-user",
            key="API_KEY",
            value="secret",
        )

        assert entry["key"] == "API_KEY"
        assert entry["value"] == "secret"
        assert entry["project_id"] == project_id
        assert entry["id"]

        env = await get_project_environments(project_id)
        assert env == {"API_KEY": "secret"}

    @pytest.mark.asyncio
    async def test_upsert_updates_existing_entry(self, faker, setup_test_db):
        project_id = (
            await create_project(
                user_id="test-user",
                name=faker.unique.word(),
                repository_url="https://github.com/owner/repo",
                repository_owner="owner",
                repository_name="repo",
            )
        )["id"]

        await upsert_project_environment(
            project_id=project_id,
            user_id="test-user",
            key="API_KEY",
            value="first",
        )
        second = await upsert_project_environment(
            project_id=project_id,
            user_id="test-user",
            key="API_KEY",
            value="second",
        )

        assert second["value"] == "second"
        env = await get_project_environments(project_id)
        assert env == {"API_KEY": "second"}

    @pytest.mark.asyncio
    async def test_upsert_raises_for_missing_project(self, setup_test_db):
        with pytest.raises(LookupError):
            await upsert_project_environment(
                project_id="nonexistent",
                user_id="test-user",
                key="X",
                value="Y",
            )

    @pytest.mark.asyncio
    async def test_delete_removes_entry(self, faker, setup_test_db):
        project_id = (
            await create_project(
                user_id="test-user",
                name=faker.unique.word(),
                repository_url="https://github.com/owner/repo",
                repository_owner="owner",
                repository_name="repo",
            )
        )["id"]
        await upsert_project_environment(
            project_id=project_id,
            user_id="test-user",
            key="API_KEY",
            value="secret",
        )

        await delete_project_environment(
            project_id=project_id,
            user_id="test-user",
            key="API_KEY",
        )

        env = await get_project_environments(project_id)
        assert env == {}

    @pytest.mark.asyncio
    async def test_delete_raises_for_missing_project(self, setup_test_db):
        with pytest.raises(LookupError):
            await delete_project_environment(
                project_id="nonexistent",
                user_id="test-user",
                key="X",
            )

    @pytest.mark.asyncio
    async def test_delete_is_noop_for_missing_key(self, faker, setup_test_db):
        project_id = (
            await create_project(
                user_id="test-user",
                name=faker.unique.word(),
                repository_url="https://github.com/owner/repo",
                repository_owner="owner",
                repository_name="repo",
            )
        )["id"]

        await delete_project_environment(
            project_id=project_id,
            user_id="test-user",
            key="NOPE",
        )

        env = await get_project_environments(project_id)
        assert env == {}

    @pytest.mark.asyncio
    async def test_delete_project_by_non_owner_leaves_environment_intact(self, faker, setup_test_db):
        project_id = (
            await create_project(
                user_id="owner-user",
                name=faker.unique.word(),
                repository_url="https://github.com/owner/repo",
                repository_owner="owner",
                repository_name="repo",
            )
        )["id"]
        await upsert_project_environment(
            project_id=project_id,
            user_id="owner-user",
            key="API_KEY",
            value="secret",
        )

        # A different user must not be able to delete the project or wipe its env vars.
        await delete_project(project_id=project_id, user_id="attacker-user")

        env = await get_project_environments(project_id)
        assert env == {"API_KEY": "secret"}


class TestProjectEnvironmentType:
    @pytest.fixture(autouse=True)
    def _encryption_keys(self):
        with (
            patch("demetra.services.persistence.encryption.DEMETRA_SECRET_KEY", _TEST_SECRET_KEY),
            patch("demetra.services.persistence.encryption.ENCRYPTION_SALT", _TEST_ENCRYPTION_SALT),
            patch("demetra.services.persistence.encryption.get_fernet", return_value=_TEST_FERNET),
        ):
            yield

    @pytest.mark.asyncio
    async def test_default_type_is_text(self, faker, setup_test_db):
        project_id = (
            await create_project(
                user_id="test-user",
                name=faker.unique.word(),
                repository_url="https://github.com/owner/repo",
                repository_owner="owner",
                repository_name="repo",
            )
        )["id"]

        entry = await upsert_project_environment(
            project_id=project_id,
            user_id="test-user",
            key="API_URL",
            value="https://example.com",
        )

        assert entry["type"] == "text"
        assert entry["value"] == "https://example.com"

    @pytest.mark.asyncio
    async def test_encrypted_value_is_stored_encrypted(self, faker, setup_test_db):
        project_id = (
            await create_project(
                user_id="test-user",
                name=faker.unique.word(),
                repository_url="https://github.com/owner/repo",
                repository_owner="owner",
                repository_name="repo",
            )
        )["id"]

        entry = await upsert_project_environment(
            project_id=project_id,
            user_id="test-user",
            key="API_KEY",
            value="topsecret",
            env_type="encrypted",
        )

        assert entry["type"] == "encrypted"
        assert entry["value"] == "********"

        async with _get_connection() as conn:
            row = (
                await conn.execute(
                    select(project_environments).where(
                        (project_environments.c.project_id == project_id) & (project_environments.c.key == "API_KEY")
                    )
                )
            ).fetchone()
        assert row is not None
        assert row.type == "encrypted"
        assert row.value != "topsecret"
        assert decrypt_str(row.value) == "topsecret"

    @pytest.mark.asyncio
    async def test_get_environments_decrypts_encrypted_values(self, faker, setup_test_db):
        project_id = (
            await create_project(
                user_id="test-user",
                name=faker.unique.word(),
                repository_url="https://github.com/owner/repo",
                repository_owner="owner",
                repository_name="repo",
            )
        )["id"]

        await upsert_project_environment(
            project_id=project_id,
            user_id="test-user",
            key="API_KEY",
            value="topsecret",
            env_type="encrypted",
        )
        await upsert_project_environment(
            project_id=project_id,
            user_id="test-user",
            key="API_URL",
            value="https://example.com",
            env_type="text",
        )

        env = await get_project_environments(project_id)

        assert env == {"API_KEY": "topsecret", "API_URL": "https://example.com"}

    @pytest.mark.asyncio
    async def test_list_environments_masks_encrypted_values(self, faker, setup_test_db):
        project_id = (
            await create_project(
                user_id="test-user",
                name=faker.unique.word(),
                repository_url="https://github.com/owner/repo",
                repository_owner="owner",
                repository_name="repo",
            )
        )["id"]

        await upsert_project_environment(
            project_id=project_id,
            user_id="test-user",
            key="API_KEY",
            value="topsecret",
            env_type="encrypted",
        )
        await upsert_project_environment(
            project_id=project_id,
            user_id="test-user",
            key="API_URL",
            value="https://example.com",
            env_type="text",
        )

        entries = await list_project_environments(project_id=project_id, user_id="test-user")

        by_key = {entry["key"]: entry for entry in entries}
        assert by_key["API_KEY"]["value"] == "********"
        assert by_key["API_KEY"]["type"] == "encrypted"
        assert by_key["API_URL"]["value"] == "https://example.com"
        assert by_key["API_URL"]["type"] == "text"

    @pytest.mark.asyncio
    async def test_upsert_can_switch_type(self, faker, setup_test_db):
        project_id = (
            await create_project(
                user_id="test-user",
                name=faker.unique.word(),
                repository_url="https://github.com/owner/repo",
                repository_owner="owner",
                repository_name="repo",
            )
        )["id"]

        await upsert_project_environment(
            project_id=project_id,
            user_id="test-user",
            key="API_KEY",
            value="topsecret",
            env_type="text",
        )
        entry = await upsert_project_environment(
            project_id=project_id,
            user_id="test-user",
            key="API_KEY",
            value="topsecret",
            env_type="encrypted",
        )

        assert entry["type"] == "encrypted"
        assert entry["value"] == "********"

        env = await get_project_environments(project_id)
        assert env == {"API_KEY": "topsecret"}

    @pytest.mark.asyncio
    async def test_list_environments_raises_for_missing_project(self, setup_test_db):
        with pytest.raises(LookupError):
            await list_project_environments(project_id="missing", user_id="test-user")


class TestUserEnvironments:
    @pytest.mark.asyncio
    async def test_get_user_environments_returns_empty_dict_when_none(self, setup_test_db):
        result = await get_user_environments_decrypted("nonexistent-user")
        assert result == {}

    @pytest.mark.asyncio
    async def test_upsert_creates_new_entry(self, faker, setup_test_db):
        user_id = await create_user(email=f"{faker.unique.word()}@example.com", github_id=f"git-{uuid4().hex[:8]}")

        entry = await upsert_user_environment(
            user_id=user_id,
            key="SHARED_KEY",
            value="shared-value",
        )

        assert entry["key"] == "SHARED_KEY"
        assert entry["value"] == "shared-value"
        assert entry["user_id"] == user_id
        assert entry["id"]

        env = await get_user_environments_decrypted(user_id=user_id)
        assert env == {"SHARED_KEY": "shared-value"}

    @pytest.mark.asyncio
    async def test_upsert_updates_existing_entry(self, faker, setup_test_db):
        user_id = await create_user(email=f"{faker.unique.word()}@example.com", github_id=f"git-{uuid4().hex[:8]}")

        await upsert_user_environment(user_id=user_id, key="SHARED_KEY", value="first")
        second = await upsert_user_environment(user_id=user_id, key="SHARED_KEY", value="second")

        assert second["value"] == "second"
        env = await get_user_environments_decrypted(user_id=user_id)
        assert env == {"SHARED_KEY": "second"}

    @pytest.mark.asyncio
    async def test_upsert_raises_for_missing_user(self, setup_test_db):
        with pytest.raises(LookupError):
            await upsert_user_environment(user_id="nonexistent", key="X", value="Y")

    @pytest.mark.asyncio
    async def test_delete_removes_entry(self, faker, setup_test_db):
        user_id = await create_user(email=f"{faker.unique.word()}@example.com", github_id=f"git-{uuid4().hex[:8]}")
        await upsert_user_environment(user_id=user_id, key="SHARED_KEY", value="secret")

        await delete_user_environment(user_id=user_id, key="SHARED_KEY")

        env = await get_user_environments_decrypted(user_id=user_id)
        assert env == {}

    @pytest.mark.asyncio
    async def test_delete_raises_for_missing_user(self, setup_test_db):
        with pytest.raises(LookupError):
            await delete_user_environment(user_id="nonexistent", key="X")

    @pytest.mark.asyncio
    async def test_user_env_is_isolated_between_users(self, faker, setup_test_db):
        user_a = await create_user(email=f"{faker.unique.word()}@example.com", github_id=f"git-{uuid4().hex[:8]}")
        user_b = await create_user(email=f"{faker.unique.word()}@example.com", github_id=f"git-{uuid4().hex[:8]}")

        await upsert_user_environment(user_id=user_a, key="ONLY_A", value="value_a")
        await upsert_user_environment(user_id=user_b, key="ONLY_B", value="value_b")

        env_a = await get_user_environments_decrypted(user_id=user_a)
        env_b = await get_user_environments_decrypted(user_id=user_b)
        assert env_a == {"ONLY_A": "value_a"}
        assert env_b == {"ONLY_B": "value_b"}

    @pytest.mark.asyncio
    async def test_user_env_is_isolated_from_project_env(self, faker, setup_test_db):
        user_id = await create_user(email=f"{faker.unique.word()}@example.com", github_id=f"git-{uuid4().hex[:8]}")
        project_id = (
            await create_project(
                user_id=user_id,
                name=faker.unique.word(),
                repository_url="https://github.com/owner/repo",
                repository_owner="owner",
                repository_name="repo",
            )
        )["id"]

        await upsert_user_environment(user_id=user_id, key="SHARED", value="user-value")
        await upsert_project_environment(
            project_id=project_id,
            user_id=user_id,
            key="PROJECT_ONLY",
            value="project-value",
        )

        user_env = await get_user_environments_decrypted(user_id=user_id)
        project_env = await get_project_environments(project_id=project_id)
        assert user_env == {"SHARED": "user-value"}
        assert project_env == {"PROJECT_ONLY": "project-value"}

    @pytest.mark.asyncio
    async def test_delete_project_keeps_user_env(self, faker, setup_test_db):
        user_id = await create_user(email=f"{faker.unique.word()}@example.com", github_id=f"git-{uuid4().hex[:8]}")
        project_id = (
            await create_project(
                user_id=user_id,
                name=faker.unique.word(),
                repository_url="https://github.com/owner/repo",
                repository_owner="owner",
                repository_name="repo",
            )
        )["id"]
        await upsert_user_environment(user_id=user_id, key="SHARED", value="user-value")

        await delete_project(project_id=project_id, user_id=user_id)

        user_env = await get_user_environments_decrypted(user_id=user_id)
        assert user_env == {"SHARED": "user-value"}


class TestUserEnvironmentType:
    @pytest.fixture(autouse=True)
    def _encryption_keys(self):
        with (
            patch("demetra.services.persistence.encryption.DEMETRA_SECRET_KEY", _TEST_SECRET_KEY),
            patch("demetra.services.persistence.encryption.ENCRYPTION_SALT", _TEST_ENCRYPTION_SALT),
            patch("demetra.services.persistence.encryption.get_fernet", return_value=_TEST_FERNET),
        ):
            yield

    @pytest.mark.asyncio
    async def test_encrypted_value_is_stored_encrypted(self, faker, setup_test_db):
        user_id = await create_user(email=f"{faker.unique.word()}@example.com", github_id=f"git-{uuid4().hex[:8]}")

        entry = await upsert_user_environment(
            user_id=user_id,
            key="API_TOKEN",
            value="topsecret",
            env_type="encrypted",
        )

        assert entry["type"] == "encrypted"
        assert entry["value"] == "********"

        async with _get_connection() as conn:
            row = (
                await conn.execute(
                    select(project_environments).where(
                        (project_environments.c.user_id == user_id)
                        & (project_environments.c.key == "API_TOKEN")
                        & (project_environments.c.scope == "user")
                    )
                )
            ).fetchone()
        assert row is not None
        assert row.type == "encrypted"
        assert row.value != "topsecret"
        assert decrypt_str(row.value) == "topsecret"

    @pytest.mark.asyncio
    async def test_list_environments_masks_encrypted_values(self, faker, setup_test_db):
        user_id = await create_user(email=f"{faker.unique.word()}@example.com", github_id=f"git-{uuid4().hex[:8]}")

        await upsert_user_environment(
            user_id=user_id,
            key="API_TOKEN",
            value="topsecret",
            env_type="encrypted",
        )
        await upsert_user_environment(
            user_id=user_id,
            key="API_URL",
            value="https://example.com",
            env_type="text",
        )

        entries = await list_user_environments(user_id=user_id)

        by_key = {entry["key"]: entry for entry in entries}
        assert by_key["API_TOKEN"]["value"] == "********"
        assert by_key["API_TOKEN"]["type"] == "encrypted"
        assert by_key["API_URL"]["value"] == "https://example.com"
        assert by_key["API_URL"]["type"] == "text"

    @pytest.mark.asyncio
    async def test_list_environments_masks_sensitive_plaintext_keys(self, faker, setup_test_db):
        user_id = await create_user(email=f"{faker.unique.word()}@example.com", github_id=f"git-{uuid4().hex[:8]}")

        await upsert_user_environment(
            user_id=user_id,
            key="STRIPE_API_KEY",
            value="sk_live_123",
            env_type="text",
        )
        await upsert_user_environment(
            user_id=user_id,
            key="DATABASE_URL",
            value="postgres://localhost/db",
            env_type="text",
        )

        entries = await list_user_environments(user_id=user_id)

        by_key = {entry["key"]: entry for entry in entries}
        assert by_key["STRIPE_API_KEY"]["value"] == "********"
        assert by_key["STRIPE_API_KEY"]["type"] == "text"
        assert by_key["DATABASE_URL"]["value"] == "postgres://localhost/db"

    @pytest.mark.asyncio
    async def test_get_user_environments_decrypts_encrypted_values(self, faker, setup_test_db):
        user_id = await create_user(email=f"{faker.unique.word()}@example.com", github_id=f"git-{uuid4().hex[:8]}")

        await upsert_user_environment(
            user_id=user_id,
            key="API_TOKEN",
            value="topsecret",
            env_type="encrypted",
        )
        await upsert_user_environment(
            user_id=user_id,
            key="API_URL",
            value="https://example.com",
            env_type="text",
        )

        env = await get_user_environments_decrypted(user_id=user_id)

        assert env == {"API_TOKEN": "topsecret", "API_URL": "https://example.com"}


class TestRunAttempts:
    @pytest.fixture(autouse=True)
    def _setup_db(self, setup_test_db):
        pass

    @pytest.mark.asyncio
    async def test_run_attempts_starts_at_0_on_insert(
        self,
        db_task_id: str,
    ):
        session = await upsert_pending_session(task_id=db_task_id, session_id=None)
        assert session.run_attempts == 0

        found = await get_session(db_task_id)
        assert found is not None
        assert found.run_attempts == 0

    @pytest.mark.asyncio
    async def test_increment_run_attempts(
        self,
        db_task_id: str,
    ):
        await upsert_pending_session(task_id=db_task_id, session_id=None)

        first = await increment_run_attempts(db_task_id)
        assert first == 1

        second = await increment_run_attempts(db_task_id)
        assert second == 2

        third = await increment_run_attempts(db_task_id)
        assert third == 3

        found = await get_session(db_task_id)
        assert found is not None
        assert found.run_attempts == 3

    @pytest.mark.asyncio
    async def test_run_attempts_preserved_on_upsert(
        self,
        db_task_id: str,
    ):
        await upsert_pending_session(task_id=db_task_id, session_id=None)
        await increment_run_attempts(db_task_id)

        # Re-upsert should preserve (not reset) run_attempts
        await upsert_pending_session(task_id=db_task_id, session_id="new-session-id")

        found = await get_session(db_task_id)
        assert found is not None
        assert found.run_attempts == 1

    @pytest.mark.asyncio
    async def test_step_preserved_on_re_upsert(
        self,
        db_task_id: str,
    ):
        await upsert_pending_session(task_id=db_task_id, session_id=None)
        await update_session_step(db_task_id, "build")

        await upsert_pending_session(task_id=db_task_id, session_id="new-session-id")

        found = await get_session(db_task_id)
        assert found is not None
        assert found.step == "build"


class TestListenerAttempts:
    @pytest.fixture(autouse=True)
    def _setup_db(self, setup_test_db):
        pass

    @pytest.mark.asyncio
    async def test_listener_attempts_starts_at_0_on_insert(
        self,
        db_task_id: str,
    ):
        session = await upsert_pending_session(task_id=db_task_id, session_id=None)
        assert session.listener_attempts == 0

        found = await get_session(db_task_id)
        assert found is not None
        assert found.listener_attempts == 0

    @pytest.mark.asyncio
    async def test_increment_listener_attempts(
        self,
        db_task_id: str,
    ):
        await upsert_pending_session(task_id=db_task_id, session_id=None)

        first = await increment_listener_attempts(db_task_id)
        assert first == 1

        second = await increment_listener_attempts(db_task_id)
        assert second == 2

        third = await increment_listener_attempts(db_task_id)
        assert third == 3

        found = await get_session(db_task_id)
        assert found is not None
        assert found.listener_attempts == 3

    @pytest.mark.asyncio
    async def test_reset_listener_attempts(
        self,
        db_task_id: str,
    ):
        await upsert_pending_session(task_id=db_task_id, session_id=None)
        await increment_listener_attempts(db_task_id)
        await increment_listener_attempts(db_task_id)

        result = await reset_listener_attempts(db_task_id)
        assert result == 0

        found = await get_session(db_task_id)
        assert found is not None
        assert found.listener_attempts == 0

    @pytest.mark.asyncio
    async def test_listener_attempts_preserved_on_upsert(
        self,
        db_task_id: str,
    ):
        await upsert_pending_session(task_id=db_task_id, session_id=None)
        await increment_listener_attempts(db_task_id)

        await upsert_pending_session(task_id=db_task_id, session_id="new-session-id")

        found = await get_session(db_task_id)
        assert found is not None
        assert found.listener_attempts == 1

    @pytest.mark.asyncio
    async def test_increment_listener_attempts_nonexistent_returns_0(self):
        result = await increment_listener_attempts("NONEXISTENT-TASK-999")
        assert result == 0

    @pytest.mark.asyncio
    async def test_reset_listener_attempts_nonexistent_returns_0(self):
        result = await reset_listener_attempts("NONEXISTENT-TASK-999")
        assert result == 0


class TestLinearLink:
    @pytest.fixture(autouse=True)
    def _setup_db(self, setup_test_db):
        pass

    @pytest.mark.asyncio
    async def test_linear_link_defaults_to_none(
        self,
        db_task_id: str,
    ):
        await upsert_pending_session(task_id=db_task_id, session_id=None)

        found = await get_session(db_task_id)
        assert found is not None
        assert found.linear_link is None

    @pytest.mark.asyncio
    async def test_save_session_stores_linear_link(
        self,
        db_task_id: str,
        db_session_id: str,
    ):
        url = "https://linear.app/manti-by/issue/MNT-123"
        session = await save_session(task_id=db_task_id, session_id=db_session_id, build_plan="plan", linear_link=url)

        assert session.linear_link == url

        found = await get_session(db_task_id)
        assert found is not None
        assert found.linear_link == url

    @pytest.mark.asyncio
    async def test_update_session_linear_link_persists_value(
        self,
        db_task_id: str,
    ):
        await upsert_pending_session(task_id=db_task_id, session_id=None)

        await update_session_linear_link(task_id=db_task_id, linear_link="https://linear.app/manti-by/issue/MNT-456")

        found = await get_session(db_task_id)
        assert found is not None
        assert found.linear_link == "https://linear.app/manti-by/issue/MNT-456"

    @pytest.mark.asyncio
    async def test_linear_link_preserved_on_save_without_link(
        self,
        db_task_id: str,
        db_session_id: str,
    ):
        url = "https://linear.app/manti-by/issue/MNT-789"
        await save_session(task_id=db_task_id, session_id=db_session_id, build_plan="Plan A", linear_link=url)
        await save_session(task_id=db_task_id, session_id=db_session_id, build_plan="Plan B")

        found = await get_session(db_task_id)
        assert found is not None
        assert found.build_plan == "Plan B"
        assert found.linear_link == url


class TestPrLink:
    @pytest.fixture(autouse=True)
    def _setup_db(self, setup_test_db):
        pass

    @pytest.mark.asyncio
    async def test_pr_link_defaults_to_none(
        self,
        db_task_id: str,
    ):
        await upsert_pending_session(task_id=db_task_id, session_id=None)

        found = await get_session(db_task_id)
        assert found is not None
        assert found.pr_link is None

    @pytest.mark.asyncio
    async def test_update_session_pr_link_persists_value(
        self,
        db_task_id: str,
    ):
        await upsert_pending_session(task_id=db_task_id, session_id=None)

        await update_session_pr_link(task_id=db_task_id, pr_link="https://github.com/owner/repo/pull/42")

        found = await get_session(db_task_id)
        assert found is not None
        assert found.pr_link == "https://github.com/owner/repo/pull/42"


class TestSessionHistory:
    @pytest.fixture(autouse=True)
    def _setup_db(self, setup_test_db):
        pass

    @pytest.mark.asyncio
    async def test_record_session_history_inserts_row(self, db_session_id: str):
        history = await record_session_history(
            session_id=db_session_id,
            step="build",
            length=12345,
        )
        assert history.session_id == db_session_id
        assert history.step == "build"
        assert history.length == 12345
        assert history.id is not None
        assert history.created_at is not None

    @pytest.mark.asyncio
    async def test_record_session_history_with_none_length(self, db_session_id: str):
        history = await record_session_history(
            session_id=db_session_id,
            step="plan",
            length=None,
        )
        assert history.session_id == db_session_id
        assert history.step == "plan"
        assert history.length is None

    @pytest.mark.asyncio
    async def test_get_session_history_returns_ordered_rows(self, db_session_id: str):
        await record_session_history(session_id=db_session_id, step="plan", length=100)
        await record_session_history(session_id=db_session_id, step="build", length=200)
        await record_session_history(session_id=db_session_id, step="review", length=350)

        rows = await get_session_history(db_session_id)
        assert len(rows) == 3
        steps = [r.step for r in rows]
        assert steps == ["plan", "build", "review"]
        lengths = [r.length for r in rows]
        assert lengths == [100, 200, 350]

    @pytest.mark.asyncio
    async def test_get_session_history_returns_empty_for_unknown(self):
        rows = await get_session_history("nonexistent-session")
        assert rows == []

    @pytest.mark.asyncio
    async def test_multiple_sessions_are_isolated(self, db_session_id: str):
        other_session_id = "session-other"
        await record_session_history(session_id=db_session_id, step="build", length=111)
        await record_session_history(session_id=other_session_id, step="plan", length=222)

        rows_a = await get_session_history(db_session_id)
        assert len(rows_a) == 1
        assert rows_a[0].length == 111

        rows_b = await get_session_history(other_session_id)
        assert len(rows_b) == 1
        assert rows_b[0].length == 222

    @pytest.mark.asyncio
    async def test_generates_unique_ids(self, db_session_id: str):
        h1 = await record_session_history(session_id=db_session_id, step="a", length=1)
        h2 = await record_session_history(session_id=db_session_id, step="b", length=2)
        assert h1.id != h2.id

    @pytest.mark.asyncio
    async def test_persists_context_tokens_and_model(self, db_session_id: str):
        history = await record_session_history(
            session_id=db_session_id,
            step="build",
            length=1000,
            context_tokens=500,
            model="opencode-go/deepseek-v4-flash",
        )
        assert history.context_tokens == 500
        assert history.model == "opencode-go/deepseek-v4-flash"

        rows = await get_session_history(db_session_id)
        assert len(rows) == 1
        assert rows[0].context_tokens == 500
        assert rows[0].model == "opencode-go/deepseek-v4-flash"

    @pytest.mark.asyncio
    async def test_context_tokens_defaults_to_none(self, db_session_id: str):
        history = await record_session_history(
            session_id=db_session_id,
            step="plan",
            length=1000,
        )
        assert history.context_tokens is None
        assert history.model is None

        rows = await get_session_history(db_session_id)
        assert rows[0].context_tokens is None
        assert rows[0].model is None


class TestGetSessionIdByTaskId:
    @pytest.fixture(autouse=True)
    def _setup_db(self, setup_test_db):
        pass

    @pytest.mark.asyncio
    async def test_returns_session_id_for_known_task(self, db_task_id: str, db_session_id: str):
        await create_session(task_id=db_task_id, session_id=db_session_id)
        session_id = await get_session_id_by_task_id(task_id=db_task_id)
        assert session_id == db_session_id

    @pytest.mark.asyncio
    async def test_returns_none_for_unknown_task(self):
        session_id = await get_session_id_by_task_id(task_id="nonexistent")
        assert session_id is None

    @pytest.mark.asyncio
    async def test_returns_none_when_session_id_is_empty(self, db_task_id: str):
        await upsert_pending_session(task_id=db_task_id, session_id=None)
        session_id = await get_session_id_by_task_id(task_id=db_task_id)
        assert session_id is None
