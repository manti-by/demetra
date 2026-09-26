from pathlib import Path
from unittest.mock import patch

import pytest

from demetra.library.exceptions import EnvironmentConfigError
from demetra.library.models import Context, LinearTask, Project, SessionEnvironment


OPENCODE_SETTINGS: dict = {
    "path": Path("/bin/opencode"),
    "plan_model": "settings/plan",
    "build_model": "settings/build",
    "resolve_model": "settings/resolve",
    "validate_model": "settings/validate",
    "research_model": "settings/research",
    "review_models": ["settings/review-1", "settings/review-2"],
}

OPENROUTER_SETTINGS: dict = {
    "api_key": "settings-key",
    "model": "settings/model",
    "base_url": "https://openrouter.example/v1",
}

LINEAR_SETTINGS: dict = {
    "team_id": "settings-team",
    "default_state": "settings-default-state",
    "states": {"todo": "settings-todo", "in_review": "settings-in-review"},
}


def _make_project(local_path: Path) -> Project:
    return Project(
        id="project-1",
        user_id="user-1",
        linear_project_id=None,
        name="test-project",
        state="active",
        repository_url="https://github.com/owner/repo",
        repository_name="repo",
        repository_owner="owner",
        local_path=local_path,
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )


@pytest.fixture
def settings_defaults():
    with (
        patch("demetra.settings.OPENCODE", OPENCODE_SETTINGS),
        patch("demetra.settings.OPENROUTER", OPENROUTER_SETTINGS),
        patch("demetra.settings.LINEAR", LINEAR_SETTINGS),
    ):
        yield


class TestSessionEnvironmentGet:
    def test_project_value_wins_over_user_and_settings(self, settings_defaults):
        environment = SessionEnvironment(
            project_environment={"OPENCODE_PLAN_MODEL": "project/plan"},
            user_environment={"OPENCODE_PLAN_MODEL": "user/plan"},
        )

        assert environment.get("OPENCODE_PLAN_MODEL") == "project/plan"

    def test_user_value_wins_over_settings(self, settings_defaults):
        environment = SessionEnvironment(
            project_environment={},
            user_environment={"OPENCODE_PLAN_MODEL": "user/plan"},
        )

        assert environment.get("OPENCODE_PLAN_MODEL") == "user/plan"

    def test_settings_default_used_when_both_layers_missing(self, settings_defaults):
        environment = SessionEnvironment(project_environment={}, user_environment={})

        assert environment.get("OPENCODE_PLAN_MODEL") == "settings/plan"

    def test_empty_values_fall_through_to_settings(self, settings_defaults):
        environment = SessionEnvironment(
            project_environment={"OPENCODE_PLAN_MODEL": ""},
            user_environment={"OPENCODE_PLAN_MODEL": ""},
        )

        assert environment.get("OPENCODE_PLAN_MODEL") == "settings/plan"

    def test_raises_when_no_layer_defines_the_key(self, settings_defaults):
        environment = SessionEnvironment(project_environment={}, user_environment={})

        with pytest.raises(EnvironmentConfigError, match="UNKNOWN_KEY"):
            environment.get("UNKNOWN_KEY")


class TestSessionEnvironmentModels:
    def test_opencode_models_resolve_project_over_user_over_settings(self, settings_defaults):
        environment = SessionEnvironment(
            project_environment={"OPENCODE_BUILD_MODEL": "project/build"},
            user_environment={"OPENCODE_BUILD_MODEL": "user/build"},
        )

        assert environment.opencode_build_model == "project/build"

    @pytest.mark.parametrize(
        ("property_name", "settings_value"),
        [
            ("opencode_plan_model", "settings/plan"),
            ("opencode_build_model", "settings/build"),
            ("opencode_resolve_model", "settings/resolve"),
            ("opencode_validate_model", "settings/validate"),
            ("opencode_research_model", "settings/research"),
        ],
    )
    def test_opencode_models_fall_back_to_settings(self, settings_defaults, property_name, settings_value):
        environment = SessionEnvironment(project_environment={}, user_environment={})

        assert getattr(environment, property_name) == settings_value


class TestSessionEnvironmentOpenRouter:
    def test_reads_api_key_and_model_from_layers(self, settings_defaults):
        environment = SessionEnvironment(
            project_environment={"OPENROUTER_MODEL": "project/model"},
            user_environment={"OPENROUTER_API_KEY": "user-key"},
        )

        assert environment.openrouter_config == {
            "api_key": "user-key",
            "model": "project/model",
            "base_url": OPENROUTER_SETTINGS["base_url"],
        }

    def test_base_url_always_comes_from_settings(self, settings_defaults):
        environment = SessionEnvironment(
            project_environment={"OPENROUTER_BASE_URL": "https://project.example"},
            user_environment={},
        )

        assert environment.openrouter_config["base_url"] == OPENROUTER_SETTINGS["base_url"]

    def test_raises_when_base_url_missing(self):
        with patch("demetra.settings.OPENROUTER", {"api_key": "k", "model": "m", "base_url": ""}):
            environment = SessionEnvironment(project_environment={}, user_environment={})

            with pytest.raises(EnvironmentConfigError, match="OPENROUTER_BASE_URL"):
                _ = environment.openrouter_config


class TestSessionEnvironmentLinear:
    def test_linear_state_reads_user_override(self, settings_defaults):
        environment = SessionEnvironment(
            project_environment={},
            user_environment={"LINEAR_STATE_TODO_ID": "user-todo"},
        )

        assert environment.linear_state("todo") == "user-todo"

    def test_linear_state_falls_back_to_settings(self, settings_defaults):
        environment = SessionEnvironment(project_environment={}, user_environment={})

        assert environment.linear_state("todo") == LINEAR_SETTINGS["states"]["todo"]

    def test_linear_value_team_id(self, settings_defaults):
        environment = SessionEnvironment(
            project_environment={},
            user_environment={"LINEAR_TEAM_ID": "user-team"},
        )

        assert environment.linear_value("team_id") == "user-team"

    def test_linear_value_default_state_reads_default_state_key(self, settings_defaults):
        environment = SessionEnvironment(
            project_environment={},
            user_environment={"LINEAR_DEFAULT_STATE_ID": "user-default-state"},
        )

        assert environment.linear_value("default_state") == "user-default-state"


class TestContextEnvironment:
    def test_builds_environment_from_project_layers(self, settings_defaults, tmp_path):
        project = _make_project(local_path=tmp_path)
        project.environment = {"OPENCODE_PLAN_MODEL": "project/plan"}
        project.user_environment = {"OPENROUTER_API_KEY": "user-key"}
        context = Context(
            project=project,
            auto_mode=True,
            linear_task=LinearTask(
                id="task-1",
                identifier="MNT-1",
                title="Test",
                description="desc",
                priority=1,
                created_at="2026-01-01T00:00:00Z",
            ),
            branch_name="feature/test",
            worktree_path=tmp_path,
            session=None,
        )

        assert context.environment.opencode_plan_model == "project/plan"
        assert context.environment.openrouter_config["api_key"] == "user-key"

    def test_environment_is_cached(self, settings_defaults, tmp_path):
        project = _make_project(local_path=tmp_path)
        context = Context(
            project=project,
            auto_mode=True,
            linear_task=LinearTask(
                id="task-1",
                identifier="MNT-1",
                title="Test",
                description="desc",
                priority=1,
                created_at="2026-01-01T00:00:00Z",
            ),
            branch_name="feature/test",
            worktree_path=tmp_path,
            session=None,
        )

        assert context.environment is context.environment
