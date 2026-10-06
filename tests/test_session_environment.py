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

LANGSMITH_SETTINGS: dict = {
    "tracing": False,
    "endpoint": "https://api.smith.langchain.com",
    "api_key": None,
    "project": "settings-project",
}

LINEAR_SETTINGS: dict = {
    "team_id": "settings-team",
    "default_state": "settings-default-state",
    "states": {"todo": "settings-todo", "in_review": "settings-in-review"},
}

TRACING_DEFAULTS: dict[str, str] = {
    "LANGSMITH_TRACING": "false",
    "TRACE_TO_LANGSMITH": "false",
    "LANGSMITH_ENDPOINT": "https://api.smith.langchain.com",
    "LANGSMITH_API_KEY": "",
    "LANGSMITH_PROJECT": "settings-project",
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
        patch("demetra.settings.LANGSMITH", LANGSMITH_SETTINGS),
        patch("demetra.settings.LINEAR", LINEAR_SETTINGS),
    ):
        yield


class TestSessionEnvironmentSubprocessEnv:
    def test_project_layer_wins_over_user_shared(self, settings_defaults):
        environment = SessionEnvironment(
            project_environment={"KEY": "project-value", "PROJECT_ONLY": "project-only"},
            user_environment={"KEY": "user-value", "USER_ONLY": "user-only"},
        )

        env = environment.subprocess_env
        assert env["KEY"] == "project-value"
        assert env["PROJECT_ONLY"] == "project-only"
        assert env["USER_ONLY"] == "user-only"

    def test_empty_layers_still_resolve_the_tracing_vars(self, settings_defaults):
        env = SessionEnvironment(project_environment={}, user_environment={}).subprocess_env

        assert env == TRACING_DEFAULTS

    def test_derived_tracing_vars_override_the_raw_layers(self, settings_defaults):
        environment = SessionEnvironment(
            project_environment={"LANGSMITH_TRACING": "true", "TRACE_TO_LANGSMITH": "raw-value"},
            user_environment={},
        )

        env = environment.subprocess_env
        assert env["LANGSMITH_TRACING"] == "false"
        assert env["TRACE_TO_LANGSMITH"] == "false"

    def test_configured_tracing_reaches_the_subprocess_env(self, settings_defaults):
        environment = SessionEnvironment(
            project_environment={"LANGSMITH_TRACING": "true", "LANGSMITH_API_KEY": "project-key"},
            user_environment={},
        )

        env = environment.subprocess_env
        assert env["LANGSMITH_TRACING"] == "true"
        assert env["TRACE_TO_LANGSMITH"] == "true"
        assert env["LANGSMITH_API_KEY"] == "project-key"

    def test_sources_are_not_mutated_by_the_merge(self, settings_defaults):
        project_environment = {"KEY": "project-value"}
        user_environment = {"KEY": "user-value", "OTHER": "other"}
        environment = SessionEnvironment(project_environment=project_environment, user_environment=user_environment)

        environment.subprocess_env["EXTRA"] = "extra"

        assert "EXTRA" not in project_environment
        assert "EXTRA" not in user_environment


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


class TestSessionEnvironmentLangSmith:
    def test_disabled_by_default_from_settings(self, settings_defaults):
        environment = SessionEnvironment(project_environment={}, user_environment={})

        assert environment.system_env == {
            "LANGSMITH_TRACING": "false",
            "TRACE_TO_LANGSMITH": "false",
            "LANGSMITH_ENDPOINT": "https://api.smith.langchain.com",
            "LANGSMITH_API_KEY": "",
            "LANGSMITH_PROJECT": "settings-project",
        }

    def test_sets_both_trace_flags_when_tracing_and_key_configured(self, settings_defaults):
        environment = SessionEnvironment(
            project_environment={"LANGSMITH_TRACING": "true", "LANGSMITH_API_KEY": "project-key"},
            user_environment={},
        )

        env = environment.system_env
        assert env["LANGSMITH_TRACING"] == "true"
        assert env["TRACE_TO_LANGSMITH"] == "true"
        assert env["LANGSMITH_API_KEY"] == "project-key"

    def test_tracing_forced_off_without_an_api_key(self, settings_defaults):
        environment = SessionEnvironment(
            project_environment={"LANGSMITH_TRACING": "true"},
            user_environment={},
        )

        env = environment.system_env
        assert env["LANGSMITH_TRACING"] == "false"
        assert env["TRACE_TO_LANGSMITH"] == "false"

    def test_project_key_wins_over_user_and_settings(self, settings_defaults):
        environment = SessionEnvironment(
            project_environment={"LANGSMITH_API_KEY": "project-key"},
            user_environment={"LANGSMITH_API_KEY": "user-key"},
        )

        assert environment.system_env["LANGSMITH_API_KEY"] == "project-key"

    def test_endpoint_and_project_are_overridable(self, settings_defaults):
        environment = SessionEnvironment(
            project_environment={
                "LANGSMITH_ENDPOINT": "https://project.example",
                "LANGSMITH_PROJECT": "project-name",
            },
            user_environment={},
        )

        env = environment.system_env
        assert env["LANGSMITH_ENDPOINT"] == "https://project.example"
        assert env["LANGSMITH_PROJECT"] == "project-name"

    def test_empty_settings_endpoint_does_not_raise(self, settings_defaults):
        """An exported-but-empty value degrades to the fallback, not an error.

        ``env_get_str`` returns the raw value when the variable is set, so
        ``LANGSMITH_ENDPOINT=`` in a ``.env`` reaches settings as ``""``.
        """
        with patch("demetra.settings.LANGSMITH", {**LANGSMITH_SETTINGS, "endpoint": ""}):
            environment = SessionEnvironment(project_environment={}, user_environment={})

            assert environment.system_env["LANGSMITH_ENDPOINT"] == ""

    def test_empty_settings_project_does_not_raise(self, settings_defaults):
        with patch("demetra.settings.LANGSMITH", {**LANGSMITH_SETTINGS, "project": ""}):
            environment = SessionEnvironment(project_environment={}, user_environment={})

            assert environment.system_env["LANGSMITH_PROJECT"] == ""

    def test_empty_project_layer_endpoint_does_not_raise(self, settings_defaults):
        """An empty project-layer value is treated as unset and falls through."""
        environment = SessionEnvironment(
            project_environment={"LANGSMITH_ENDPOINT": "", "LANGSMITH_TRACING": "  YES  "},
            user_environment={},
        )

        env = environment.system_env
        assert env["LANGSMITH_ENDPOINT"] == "https://api.smith.langchain.com"
        assert env["LANGSMITH_TRACING"] == "false"
        assert env["TRACE_TO_LANGSMITH"] == "false"

    def test_truthy_spellings_are_accepted(self, settings_defaults):
        for value in ("true", "TRUE", "1", "yes", "on", " On "):
            environment = SessionEnvironment(
                project_environment={"LANGSMITH_TRACING": value, "LANGSMITH_API_KEY": "key-1"},
                user_environment={},
            )

            assert environment.system_env["LANGSMITH_TRACING"] == "true", value
            assert environment.system_env["TRACE_TO_LANGSMITH"] == "true", value

    def test_other_spellings_leave_tracing_off(self, settings_defaults):
        for value in ("false", "0", "no", "off", "enabled", ""):
            environment = SessionEnvironment(
                project_environment={"LANGSMITH_TRACING": value, "LANGSMITH_API_KEY": "key-1"},
                user_environment={},
            )

            assert environment.system_env["LANGSMITH_TRACING"] == "false", value


class TestSessionEnvironmentLookup:
    def test_returns_the_resolved_value(self):
        environment = SessionEnvironment(
            project_environment={"KEY": "project-value"},
            user_environment={"KEY": "user-value", "OTHER": "user-only"},
        )

        assert environment.lookup(key="KEY") == "project-value"
        assert environment.lookup(key="OTHER") == "user-only"

    def test_returns_none_when_unset(self):
        environment = SessionEnvironment(project_environment={}, user_environment={})

        assert environment.lookup(key="MISSING") is None

    def test_treats_an_empty_layer_value_as_unset(self):
        environment = SessionEnvironment(project_environment={"KEY": ""}, user_environment={"OTHER": ""})

        assert environment.lookup(key="KEY") is None
        assert environment.lookup(key="OTHER") is None

    def test_get_still_raises_where_lookup_returns_none(self):
        environment = SessionEnvironment(project_environment={}, user_environment={})

        with pytest.raises(EnvironmentConfigError):
            _ = environment.get(key="MISSING")

    def test_optional_keys_resolve_through_the_env_get_helpers(self):
        from demetra.services.runtime.utils import env_get_str_from

        environment = SessionEnvironment(project_environment={"KEY": "project-value"}, user_environment={})

        assert env_get_str_from(getter=environment.lookup, name="KEY", default="fallback") == "project-value"
        assert env_get_str_from(getter=environment.lookup, name="MISSING", default="fallback") == "fallback"


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
