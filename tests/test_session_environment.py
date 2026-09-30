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

CLAUDE_SETTINGS: dict = {
    "path": Path("/bin/claude"),
    "plan_model": "settings/claude-plan",
    "plan_effort": "medium",
    "build_model": "settings/claude-build",
    "build_effort": None,
    "resolve_model": "settings/claude-resolve",
    "resolve_effort": "xhigh",
    "validate_model": "settings/claude-validate",
    "validate_effort": None,
    "research_model": "settings/claude-research",
    "research_effort": "high",
    "review_models": ["opus:xhigh"],
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
        patch("demetra.settings.CLAUDE", CLAUDE_SETTINGS),
        patch("demetra.settings.AGENT_HARNESS", "opencode"),
        patch("demetra.settings.CLAUDE_DEFAULT_MAX_BUDGET_USD", 5.0),
        patch("demetra.settings.CLAUDE_MAX_BUDGET_USD", {"plan": 5.0, "build": 15.0, "review": 5.0}),
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


class TestSessionEnvironmentAgentHarness:
    def test_project_value_wins_over_user_and_settings(self, settings_defaults):
        environment = SessionEnvironment(
            project_environment={"AGENT_HARNESS": "claude"},
            user_environment={"AGENT_HARNESS": "opencode"},
        )

        assert environment.agent_harness == "claude"

    def test_user_value_wins_over_settings(self, settings_defaults):
        environment = SessionEnvironment(project_environment={}, user_environment={"AGENT_HARNESS": "claude"})

        assert environment.agent_harness == "claude"

    def test_falls_back_to_settings_default(self, settings_defaults):
        environment = SessionEnvironment(project_environment={}, user_environment={})

        assert environment.agent_harness == "opencode"

    def test_invalid_value_raises(self, settings_defaults):
        environment = SessionEnvironment(project_environment={"AGENT_HARNESS": "bogus"}, user_environment={})

        with pytest.raises(EnvironmentConfigError, match="AGENT_HARNESS"):
            _ = environment.agent_harness


class TestSessionEnvironmentClaudeModels:
    @pytest.mark.parametrize(
        ("property_name", "settings_value"),
        [
            ("claude_plan_model", "settings/claude-plan"),
            ("claude_build_model", "settings/claude-build"),
            ("claude_resolve_model", "settings/claude-resolve"),
            ("claude_validate_model", "settings/claude-validate"),
            ("claude_research_model", "settings/claude-research"),
        ],
    )
    def test_claude_models_fall_back_to_settings(self, settings_defaults, property_name, settings_value):
        environment = SessionEnvironment(project_environment={}, user_environment={})

        assert getattr(environment, property_name) == settings_value

    def test_claude_build_model_resolves_project_over_user_over_settings(self, settings_defaults):
        environment = SessionEnvironment(
            project_environment={"CLAUDE_BUILD_MODEL": "project/build"},
            user_environment={"CLAUDE_BUILD_MODEL": "user/build"},
        )

        assert environment.claude_build_model == "project/build"

    def test_claude_plan_model_resolves_user_over_settings(self, settings_defaults):
        environment = SessionEnvironment(project_environment={}, user_environment={"CLAUDE_PLAN_MODEL": "user/plan"})

        assert environment.claude_plan_model == "user/plan"

    def test_claude_effort_falls_back_to_settings(self, settings_defaults):
        environment = SessionEnvironment(project_environment={}, user_environment={})

        assert environment.claude_effort("plan") == "medium"
        assert environment.claude_effort("resolve") == "xhigh"

    def test_claude_effort_project_override_wins(self, settings_defaults):
        environment = SessionEnvironment(project_environment={"CLAUDE_PLAN_EFFORT": "low"}, user_environment={})

        assert environment.claude_effort("plan") == "low"

    def test_claude_effort_returns_none_when_unset_anywhere(self, settings_defaults):
        environment = SessionEnvironment(project_environment={}, user_environment={})

        assert environment.claude_effort("build") is None

    def test_claude_effort_never_raises(self, settings_defaults):
        environment = SessionEnvironment(project_environment={}, user_environment={})

        # "unknown" has no settings default and no override in any layer;
        # claude_effort must swallow the EnvironmentConfigError and return None.
        assert environment.claude_effort("unknown") is None


class TestSessionEnvironmentClaudeBudget:
    def test_per_agent_override_wins(self, settings_defaults):
        environment = SessionEnvironment(project_environment={"CLAUDE_PLAN_MAX_BUDGET_USD": "9.5"}, user_environment={})

        assert environment.claude_max_budget_usd("plan") == 9.5

    def test_falls_back_to_global_default_when_no_per_agent_override(self, settings_defaults):
        environment = SessionEnvironment(project_environment={}, user_environment={})

        # "validate" has no per-agent settings entry in CLAUDE_MAX_BUDGET_USD.
        assert environment.claude_max_budget_usd("validate") == 5.0

    def test_falls_back_to_settings_per_agent_default(self, settings_defaults):
        environment = SessionEnvironment(project_environment={}, user_environment={})

        assert environment.claude_max_budget_usd("build") == 15.0

    def test_non_numeric_value_raises(self, settings_defaults):
        environment = SessionEnvironment(
            project_environment={"CLAUDE_PLAN_MAX_BUDGET_USD": "not-a-number"}, user_environment={}
        )

        with pytest.raises(EnvironmentConfigError, match="CLAUDE_PLAN_MAX_BUDGET_USD"):
            environment.claude_max_budget_usd("plan")


class TestSessionEnvironmentReviewModels:
    def test_opencode_review_models_fall_back_to_settings(self, settings_defaults):
        environment = SessionEnvironment(project_environment={}, user_environment={})

        models = environment.review_models
        assert [m.model for m in models] == OPENCODE_SETTINGS["review_models"]
        assert all(m.effort is None for m in models)

    def test_opencode_review_models_are_project_overridable(self, settings_defaults):
        """OPENCODE_REVIEW_MODELS previously bypassed SessionEnvironment entirely
        (review.py read OPENCODE["review_models"] straight from settings); this
        proves the gap is closed."""
        environment = SessionEnvironment(
            project_environment={"OPENCODE_REVIEW_MODELS": "custom/model-a,custom/model-b"},
            user_environment={},
        )

        models = environment.review_models
        assert [m.model for m in models] == ["custom/model-a", "custom/model-b"]

    def test_claude_review_models_fall_back_to_settings(self, settings_defaults):
        environment = SessionEnvironment(project_environment={"AGENT_HARNESS": "claude"}, user_environment={})

        models = environment.review_models
        assert models == [type(models[0])(model="opus", effort="xhigh")]

    def test_claude_review_models_parse_model_and_effort(self, settings_defaults):
        environment = SessionEnvironment(
            project_environment={"AGENT_HARNESS": "claude", "CLAUDE_REVIEW_MODELS": "opus:xhigh,sonnet"},
            user_environment={},
        )

        models = environment.review_models
        assert [(m.model, m.effort) for m in models] == [("opus", "xhigh"), ("sonnet", None)]

    def test_claude_review_models_invalid_effort_raises(self, settings_defaults):
        environment = SessionEnvironment(
            project_environment={"AGENT_HARNESS": "claude", "CLAUDE_REVIEW_MODELS": "opus:not-a-level"},
            user_environment={},
        )

        with pytest.raises(EnvironmentConfigError, match="not-a-level"):
            _ = environment.review_models


class TestSessionEnvironmentAgentModel:
    def test_agent_model_opencode(self, settings_defaults):
        environment = SessionEnvironment(project_environment={}, user_environment={})

        assert environment.agent_model("plan") == "settings/plan"

    def test_agent_model_claude(self, settings_defaults):
        environment = SessionEnvironment(project_environment={"AGENT_HARNESS": "claude"}, user_environment={})

        assert environment.agent_model("plan") == "settings/claude-plan"
