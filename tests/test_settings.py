from pathlib import Path

import pytest

from demetra import settings
from demetra.library.constants import OS_ENV_ALLOWLIST, SEARCH_STOP_WORDS
from demetra.library.exceptions import SettingsError


class TestSettings:
    def test_home_path_points_to_home(self):
        assert settings.HOME_PATH == Path.home()

    def test_linear_api_url_is_correct(self):
        assert settings.LINEAR["api_url"] == "https://api.linear.app/graphql"

    def test_projects_path_uses_env_or_default(self):
        assert "www" in str(settings.PROJECTS_PATH)

    def test_opencode_defaults(self, monkeypatch):
        monkeypatch.delenv("OPENCODE_PLAN_MODEL", raising=False)
        import importlib

        import demetra.settings as settings_module

        importlib.reload(settings_module)

        try:
            assert ".opencode" in str(settings_module.OPENCODE["path"])
            assert "opencode" in settings_module.OPENCODE["plan_model"]
        finally:
            importlib.reload(settings_module)

    def test_opencode_validate_model_default(self, monkeypatch):
        monkeypatch.delenv("OPENCODE_VALIDATE_MODEL", raising=False)
        import importlib

        import demetra.settings as settings_module

        importlib.reload(settings_module)

        try:
            assert "opencode" in settings_module.OPENCODE["validate_model"]
        finally:
            importlib.reload(settings_module)

    def test_opencode_validate_model_env_override(self, monkeypatch):
        monkeypatch.setenv("OPENCODE_VALIDATE_MODEL", "opencode-go/custom-validate")
        import importlib

        import demetra.settings as settings_module

        importlib.reload(settings_module)

        try:
            assert settings_module.OPENCODE["validate_model"] == "opencode-go/custom-validate"
        finally:
            monkeypatch.delenv("OPENCODE_VALIDATE_MODEL", raising=False)
            importlib.reload(settings_module)

    def test_attempts_defaults(self, monkeypatch):
        for name in (
            "MAX_RUN_ATTEMPTS",
            "MAX_PLAN_ATTEMPTS",
            "MAX_BUILD_ATTEMPTS",
            "MAX_REVIEW_ATTEMPTS",
            "MAX_MERGE_ATTEMPTS",
            "MAX_REBASE_ATTEMPTS",
            "MAX_LISTENER_ATTEMPTS",
            "MAX_RESEARCH_ATTEMPTS",
        ):
            monkeypatch.delenv(name, raising=False)
        import importlib

        import demetra.settings as settings_module

        importlib.reload(settings_module)

        try:
            assert settings_module.MAX_ATTEMPTS == {
                "run": 3,
                "plan": 10,
                "build": 10,
                "review": 5,
                "merge": 5,
                "rebase": 5,
                "listener": 5,
                "research": 5,
            }
        finally:
            importlib.reload(settings_module)

    def test_attempts_env_override(self, monkeypatch):
        monkeypatch.setenv("MAX_RUN_ATTEMPTS", "7")
        monkeypatch.setenv("MAX_PLAN_ATTEMPTS", "5")
        import importlib

        import demetra.settings as settings_module

        importlib.reload(settings_module)

        try:
            assert settings_module.MAX_ATTEMPTS["run"] == 7
            assert settings_module.MAX_ATTEMPTS["plan"] == 5
        finally:
            monkeypatch.delenv("MAX_RUN_ATTEMPTS", raising=False)
            monkeypatch.delenv("MAX_PLAN_ATTEMPTS", raising=False)
            importlib.reload(settings_module)

    def test_git_worktree_path_default(self):
        assert ".demetra/worktrees" in str(settings.GIT["worktree_path"])

    def test_settings_can_be_overridden_via_env(self, monkeypatch):
        monkeypatch.setenv("PROJECTS_PATH", "/custom/projects")
        monkeypatch.setenv("LINEAR_TEAM_ID", "test-team")

        import importlib

        import demetra.settings as settings_module

        importlib.reload(settings_module)

        try:
            assert "/custom/projects" in str(settings_module.PROJECTS_PATH)
            assert settings_module.LINEAR["team_id"] == "test-team"
        finally:
            # Restore original module state for other tests
            monkeypatch.delenv("PROJECTS_PATH", raising=False)
            monkeypatch.delenv("LINEAR_API_KEY", raising=False)
            monkeypatch.delenv("LINEAR_TEAM_ID", raising=False)
            importlib.reload(settings_module)

    def test_linear_filter_labels_default_empty(self, monkeypatch):
        monkeypatch.delenv("LINEAR_FILTER_LABELS", raising=False)

        import importlib

        import demetra.settings as settings_module

        importlib.reload(settings_module)

        try:
            assert settings_module.LINEAR["filter_labels"] == []
        finally:
            importlib.reload(settings_module)

    def test_features_defaults_disabled(self, monkeypatch):
        monkeypatch.delenv("IS_RUFF_ENABLED", raising=False)
        monkeypatch.delenv("IS_PYTEST_ENABLED", raising=False)

        import importlib

        import demetra.settings as settings_module

        importlib.reload(settings_module)

        try:
            assert settings_module.FEATURES["is_ruff_enabled"] is False
            assert settings_module.FEATURES["is_pytest_enabled"] is False
        finally:
            importlib.reload(settings_module)

    def test_features_env_override(self, monkeypatch):
        monkeypatch.setenv("IS_RUFF_ENABLED", "True")
        monkeypatch.setenv("IS_PYTEST_ENABLED", "true")

        import importlib

        import demetra.settings as settings_module

        importlib.reload(settings_module)

        try:
            assert settings_module.FEATURES["is_ruff_enabled"] is True
            assert settings_module.FEATURES["is_pytest_enabled"] is True
        finally:
            monkeypatch.delenv("IS_RUFF_ENABLED", raising=False)
            monkeypatch.delenv("IS_PYTEST_ENABLED", raising=False)
            importlib.reload(settings_module)

    def test_features_partial_override(self, monkeypatch):
        monkeypatch.setenv("IS_RUFF_ENABLED", "true")
        monkeypatch.delenv("IS_PYTEST_ENABLED", raising=False)

        import importlib

        import demetra.settings as settings_module

        importlib.reload(settings_module)

        try:
            assert settings_module.FEATURES["is_ruff_enabled"] is True
            assert settings_module.FEATURES["is_pytest_enabled"] is False
        finally:
            monkeypatch.delenv("IS_RUFF_ENABLED", raising=False)
            importlib.reload(settings_module)

    def test_os_env_allowlist_contains_expected_keys(self, monkeypatch):
        monkeypatch.delenv("OS_ENV_PROJECT_OPTINS", raising=False)

        import importlib

        import demetra.settings as settings_module

        importlib.reload(settings_module)

        try:
            assert "PATH" in OS_ENV_ALLOWLIST
            assert "HOME" in OS_ENV_ALLOWLIST
            assert "VIRTUAL_ENV" in OS_ENV_ALLOWLIST
            assert "PWD" in OS_ENV_ALLOWLIST
            assert "GITHUB_TOKEN" not in OS_ENV_ALLOWLIST
        finally:
            importlib.reload(settings_module)

    def test_os_env_allowlist_includes_ssh_and_proxy_keys(self, monkeypatch):
        monkeypatch.delenv("OS_ENV_PROJECT_OPTINS", raising=False)

        import importlib

        import demetra.settings as settings_module

        importlib.reload(settings_module)

        try:
            for key in (
                "SSH_AUTH_SOCK",
                "SSH_AGENT_PID",
                "GIT_SSH_COMMAND",
                "http_proxy",
                "https_proxy",
                "HTTP_PROXY",
                "HTTPS_PROXY",
                "NO_PROXY",
                "no_proxy",
                "all_proxy",
                "ALL_PROXY",
            ):
                assert key in OS_ENV_ALLOWLIST
        finally:
            importlib.reload(settings_module)

    def test_os_env_project_optins_default_empty(self, monkeypatch):
        monkeypatch.delenv("OS_ENV_PROJECT_OPTINS", raising=False)

        import importlib

        import demetra.settings as settings_module

        importlib.reload(settings_module)

        try:
            assert settings_module.OS_ENV_PROJECT_OPTINS == {}
        finally:
            importlib.reload(settings_module)

    def test_os_env_project_optins_parses_registry(self, monkeypatch):
        monkeypatch.setenv("OS_ENV_PROJECT_OPTINS", "project-a=GITHUB_TOKEN,GITHUB_ACTIONS;project-b=AWS_PROFILE")

        import importlib

        import demetra.settings as settings_module

        importlib.reload(settings_module)

        try:
            assert settings_module.OS_ENV_PROJECT_OPTINS == {
                "project-a": ["GITHUB_TOKEN", "GITHUB_ACTIONS"],
                "project-b": ["AWS_PROFILE"],
            }
        finally:
            monkeypatch.delenv("OS_ENV_PROJECT_OPTINS", raising=False)
            importlib.reload(settings_module)

    def test_demetra_secret_key_falls_back_to_secret_key(self, monkeypatch):
        monkeypatch.setenv("SECRET_KEY", "fallback-secret")
        monkeypatch.delenv("DEMETRA_SECRET_KEY", raising=False)

        import importlib

        import demetra.settings as settings_module

        importlib.reload(settings_module)

        try:
            assert settings_module.SECRET_KEY == "fallback-secret"
        finally:
            monkeypatch.delenv("SECRET_KEY", raising=False)
            importlib.reload(settings_module)

    def test_secret_key_env_override(self, monkeypatch):
        monkeypatch.setenv("SECRET_KEY", "dedicated-secret")

        import importlib

        import demetra.settings as settings_module

        importlib.reload(settings_module)

        try:
            assert settings_module.SECRET_KEY == "dedicated-secret"
        finally:
            monkeypatch.delenv("SECRET_KEY", raising=False)
            importlib.reload(settings_module)

    def test_wiki_budget_reads_llm_budget_files(self, monkeypatch):
        monkeypatch.setenv("WIKI_LLM_BUDGET_FILES", "5")

        import importlib

        import demetra.settings as settings_module

        importlib.reload(settings_module)

        try:
            assert settings_module.WIKI["llm_budget_files"] == 5
        finally:
            monkeypatch.delenv("WIKI_LLM_BUDGET_FILES", raising=False)
            importlib.reload(settings_module)

    def test_openrouter_base_url_default(self, monkeypatch):
        monkeypatch.delenv("OPENROUTER_BASE_URL", raising=False)

        import importlib

        import demetra.settings as settings_module

        importlib.reload(settings_module)

        try:
            assert settings_module.OPENROUTER["base_url"] == "https://openrouter.ai/api/v1"
        finally:
            importlib.reload(settings_module)

    def test_openrouter_base_url_allows_custom_https(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_BASE_URL", "https://custom.example/v1")

        import importlib

        import demetra.settings as settings_module

        importlib.reload(settings_module)

        try:
            assert settings_module.OPENROUTER["base_url"] == "https://custom.example/v1"
        finally:
            monkeypatch.delenv("OPENROUTER_BASE_URL", raising=False)
            importlib.reload(settings_module)

    def test_openrouter_base_url_allows_loopback_http(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_BASE_URL", "http://localhost:8000/v1")

        import importlib

        import demetra.settings as settings_module

        importlib.reload(settings_module)

        try:
            assert settings_module.OPENROUTER["base_url"] == "http://localhost:8000/v1"
        finally:
            monkeypatch.delenv("OPENROUTER_BASE_URL", raising=False)
            importlib.reload(settings_module)

    @pytest.mark.parametrize(
        "base_url",
        [
            "",
            "   ",
            "not a url",
            "openrouter.ai/api/v1",
            "https://",
            "http://evil.example/v1",
            "https://user:pass@evil.example/v1",
        ],
    )
    def test_openrouter_base_url_rejects_invalid(self, monkeypatch, base_url):
        monkeypatch.setenv("OPENROUTER_BASE_URL", base_url)

        import importlib

        import demetra.settings as settings_module

        with pytest.raises(SettingsError):
            importlib.reload(settings_module)
        monkeypatch.delenv("OPENROUTER_BASE_URL", raising=False)
        importlib.reload(settings_module)


class TestClaudeSettings:
    def test_claude_defaults(self, monkeypatch):
        for name in (
            "CLAUDE_PLAN_MODEL",
            "CLAUDE_PLAN_EFFORT",
            "CLAUDE_RESOLVE_MODEL",
            "CLAUDE_RESOLVE_EFFORT",
            "CLAUDE_RESEARCH_MODEL",
            "CLAUDE_RESEARCH_EFFORT",
            "CLAUDE_BUILD_MODEL",
            "CLAUDE_BUILD_EFFORT",
            "CLAUDE_VALIDATE_MODEL",
            "CLAUDE_VALIDATE_EFFORT",
            "CLAUDE_REVIEW_MODELS",
        ):
            monkeypatch.delenv(name, raising=False)
        import importlib

        import demetra.settings as settings_module

        importlib.reload(settings_module)

        try:
            assert settings_module.CLAUDE["plan_model"] == "opus"
            assert settings_module.CLAUDE["plan_effort"] == "medium"
            assert settings_module.CLAUDE["resolve_model"] == "opus"
            assert settings_module.CLAUDE["resolve_effort"] == "xhigh"
            assert settings_module.CLAUDE["research_model"] == "opus"
            assert settings_module.CLAUDE["research_effort"] == "high"
            assert settings_module.CLAUDE["build_model"] == "sonnet"
            assert settings_module.CLAUDE["build_effort"] is None
            assert settings_module.CLAUDE["validate_model"] == "haiku"
            assert settings_module.CLAUDE["validate_effort"] is None
            assert settings_module.CLAUDE["review_models"] == ["opus:xhigh"]
        finally:
            importlib.reload(settings_module)

    def test_claude_review_models_invalid_effort_raises_at_load(self, monkeypatch):
        monkeypatch.setenv("CLAUDE_REVIEW_MODELS", "opus:ultra")
        import importlib

        import demetra.settings as settings_module

        try:
            with pytest.raises(SettingsError, match="CLAUDE_REVIEW_MODELS"):
                importlib.reload(settings_module)
        finally:
            monkeypatch.delenv("CLAUDE_REVIEW_MODELS", raising=False)
            importlib.reload(settings_module)

    def test_claude_review_models_without_effort_load(self, monkeypatch):
        monkeypatch.setenv("CLAUDE_REVIEW_MODELS", "opus, sonnet:high")
        import importlib

        import demetra.settings as settings_module

        importlib.reload(settings_module)

        try:
            assert settings_module.CLAUDE["review_models"] == ["opus", "sonnet:high"]
        finally:
            monkeypatch.delenv("CLAUDE_REVIEW_MODELS", raising=False)
            importlib.reload(settings_module)

    def test_claude_plan_effort_env_override(self, monkeypatch):
        monkeypatch.setenv("CLAUDE_PLAN_EFFORT", "low")
        import importlib

        import demetra.settings as settings_module

        importlib.reload(settings_module)

        try:
            assert settings_module.CLAUDE["plan_effort"] == "low"
        finally:
            monkeypatch.delenv("CLAUDE_PLAN_EFFORT", raising=False)
            importlib.reload(settings_module)

    def test_invalid_claude_effort_raises_settings_error(self, monkeypatch):
        monkeypatch.setenv("CLAUDE_PLAN_EFFORT", "not-a-level")
        import importlib

        import demetra.settings as settings_module

        with pytest.raises(SettingsError):
            importlib.reload(settings_module)

        monkeypatch.delenv("CLAUDE_PLAN_EFFORT", raising=False)
        importlib.reload(settings_module)

    def test_agent_harness_default(self, monkeypatch):
        monkeypatch.delenv("AGENT_HARNESS", raising=False)
        import importlib

        import demetra.settings as settings_module

        importlib.reload(settings_module)

        try:
            assert settings_module.AGENT_HARNESS == "opencode"
        finally:
            importlib.reload(settings_module)

    def test_agent_harness_env_override(self, monkeypatch):
        monkeypatch.setenv("AGENT_HARNESS", "claude")
        import importlib

        import demetra.settings as settings_module

        importlib.reload(settings_module)

        try:
            assert settings_module.AGENT_HARNESS == "claude"
        finally:
            monkeypatch.delenv("AGENT_HARNESS", raising=False)
            importlib.reload(settings_module)

    def test_invalid_agent_harness_raises_settings_error(self, monkeypatch):
        monkeypatch.setenv("AGENT_HARNESS", "bogus")
        import importlib

        import demetra.settings as settings_module

        with pytest.raises(SettingsError):
            importlib.reload(settings_module)

        monkeypatch.delenv("AGENT_HARNESS", raising=False)
        importlib.reload(settings_module)

    def test_issue_tracker_default(self, monkeypatch):
        monkeypatch.delenv("ISSUE_TRACKER", raising=False)
        import importlib

        import demetra.settings as settings_module

        importlib.reload(settings_module)

        try:
            assert settings_module.ISSUE_TRACKER == "linear"
            assert settings_module.CLICKUP["api_url"] == "https://api.clickup.com/api/v2"
            assert settings_module.CLICKUP["states"]["todo"] == "to do"
        finally:
            importlib.reload(settings_module)

    def test_issue_tracker_env_override(self, monkeypatch):
        monkeypatch.setenv("ISSUE_TRACKER", "clickup")
        monkeypatch.setenv("CLICKUP_STATE_TODO", "backlog")
        import importlib

        import demetra.settings as settings_module

        importlib.reload(settings_module)

        try:
            assert settings_module.ISSUE_TRACKER == "clickup"
            assert settings_module.CLICKUP["states"]["todo"] == "backlog"
        finally:
            monkeypatch.delenv("ISSUE_TRACKER", raising=False)
            monkeypatch.delenv("CLICKUP_STATE_TODO", raising=False)
            importlib.reload(settings_module)

    def test_invalid_issue_tracker_raises_settings_error(self, monkeypatch):
        monkeypatch.setenv("ISSUE_TRACKER", "jira")
        import importlib

        import demetra.settings as settings_module

        with pytest.raises(SettingsError, match="ISSUE_TRACKER"):
            importlib.reload(settings_module)

        monkeypatch.delenv("ISSUE_TRACKER", raising=False)
        importlib.reload(settings_module)

    def test_claude_idle_timeout_below_minimum_raises(self, monkeypatch):
        monkeypatch.setenv("CLAUDE_IDLE_TIMEOUT", "100")
        import importlib

        import demetra.settings as settings_module

        with pytest.raises(SettingsError):
            importlib.reload(settings_module)

        monkeypatch.delenv("CLAUDE_IDLE_TIMEOUT", raising=False)
        importlib.reload(settings_module)

    def test_claude_idle_timeout_above_subprocess_timeout_raises(self, monkeypatch):
        monkeypatch.setenv("SUBPROCESS_TIMEOUT", "700")
        monkeypatch.setenv("CLAUDE_IDLE_TIMEOUT", "1000")
        import importlib

        import demetra.settings as settings_module

        with pytest.raises(SettingsError):
            importlib.reload(settings_module)

        monkeypatch.delenv("SUBPROCESS_TIMEOUT", raising=False)
        monkeypatch.delenv("CLAUDE_IDLE_TIMEOUT", raising=False)
        importlib.reload(settings_module)

    def test_claude_idle_timeout_valid_value_accepted(self, monkeypatch):
        monkeypatch.setenv("CLAUDE_IDLE_TIMEOUT", "700")
        import importlib

        import demetra.settings as settings_module

        importlib.reload(settings_module)

        try:
            assert settings_module.CLAUDE_IDLE_TIMEOUT == 700
        finally:
            monkeypatch.delenv("CLAUDE_IDLE_TIMEOUT", raising=False)
            importlib.reload(settings_module)


class TestSearchStopWords:
    def test_stop_words_not_in_search_settings(self):
        assert "stop_words" not in settings.SEARCH

    def test_search_stop_words_are_lowercase(self):
        assert isinstance(SEARCH_STOP_WORDS, frozenset)
        assert SEARCH_STOP_WORDS == {word.lower() for word in SEARCH_STOP_WORDS}
        assert not any(" " in word for word in SEARCH_STOP_WORDS)

    def test_search_stop_words_cover_common_english_stop_words(self):
        assert {"a", "an", "and", "in", "is", "of", "the", "to", "was", "with"} <= SEARCH_STOP_WORDS
