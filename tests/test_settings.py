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
            "MAX_CI_ATTEMPTS",
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
                "ci": 5,
            }
        finally:
            importlib.reload(settings_module)

    def test_attempts_env_override(self, monkeypatch):
        monkeypatch.setenv("MAX_RUN_ATTEMPTS", "7")
        monkeypatch.setenv("MAX_PLAN_ATTEMPTS", "5")
        monkeypatch.setenv("MAX_CI_ATTEMPTS", "2")
        import importlib

        import demetra.settings as settings_module

        importlib.reload(settings_module)

        try:
            assert settings_module.MAX_ATTEMPTS["run"] == 7
            assert settings_module.MAX_ATTEMPTS["plan"] == 5
            assert settings_module.MAX_ATTEMPTS["ci"] == 2
        finally:
            monkeypatch.delenv("MAX_RUN_ATTEMPTS", raising=False)
            monkeypatch.delenv("MAX_PLAN_ATTEMPTS", raising=False)
            monkeypatch.delenv("MAX_CI_ATTEMPTS", raising=False)
            importlib.reload(settings_module)

    def test_git_worktree_path_default(self):
        assert ".demetra/worktrees" in str(settings.GIT["worktree_path"])

    def test_worktree_cleanup_defaults_false(self, monkeypatch):
        monkeypatch.delenv("WORKTREE_CLEANUP", raising=False)

        import importlib

        import demetra.settings as settings_module

        importlib.reload(settings_module)

        try:
            assert settings_module.FEATURES["is_worktree_cleanup_enabled"] is False
        finally:
            importlib.reload(settings_module)

    def test_worktree_cleanup_env_override(self, monkeypatch):
        monkeypatch.setenv("WORKTREE_CLEANUP", "true")

        import importlib

        import demetra.settings as settings_module

        importlib.reload(settings_module)

        try:
            assert settings_module.FEATURES["is_worktree_cleanup_enabled"] is True
        finally:
            monkeypatch.delenv("WORKTREE_CLEANUP", raising=False)
            importlib.reload(settings_module)

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

    def test_wiki_budget_reads_build_plan_cap(self, monkeypatch):
        monkeypatch.setenv("WIKI_BUILD_PLAN_CAP", "500")

        import importlib

        import demetra.settings as settings_module

        importlib.reload(settings_module)

        try:
            assert settings_module.WIKI["build_plan_cap"] == 500
            assert "llm_budget_files" not in settings_module.WIKI
            assert "llm_budget_lines" not in settings_module.WIKI
        finally:
            monkeypatch.delenv("WIKI_BUILD_PLAN_CAP", raising=False)
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


class TestLangSmithSettings:
    def test_tracing_defaults_to_off(self, monkeypatch):
        monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
        monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)

        import importlib

        import demetra.settings as settings_module

        importlib.reload(settings_module)

        try:
            assert settings_module.LANGSMITH["tracing"] is False
            assert settings_module.LANGSMITH["api_key"] is None
            assert settings_module.LANGSMITH["endpoint"] == "https://api.smith.langchain.com"
            assert settings_module.LANGSMITH["project"] == "Demetra"
        finally:
            importlib.reload(settings_module)

    def test_tracing_requires_an_api_key(self, monkeypatch):
        monkeypatch.setenv("LANGSMITH_TRACING", "true")
        monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)

        import importlib

        import demetra.settings as settings_module

        importlib.reload(settings_module)

        try:
            assert settings_module.LANGSMITH["api_key"] is None
            assert settings_module.LANGSMITH["tracing"] is False
        finally:
            monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
            importlib.reload(settings_module)

    def test_tracing_on_when_key_and_flag_configured(self, monkeypatch):
        monkeypatch.setenv("LANGSMITH_TRACING", "true")
        monkeypatch.setenv("LANGSMITH_API_KEY", "test-key")

        import importlib

        import demetra.settings as settings_module

        importlib.reload(settings_module)

        try:
            assert settings_module.LANGSMITH["api_key"] == "test-key"
            assert settings_module.LANGSMITH["tracing"] is True
        finally:
            monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
            monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
            importlib.reload(settings_module)

    def test_whitespace_only_key_counts_as_missing(self, monkeypatch):
        monkeypatch.setenv("LANGSMITH_TRACING", "true")
        monkeypatch.setenv("LANGSMITH_API_KEY", "   ")

        import importlib

        import demetra.settings as settings_module

        importlib.reload(settings_module)

        try:
            assert settings_module.LANGSMITH["api_key"] is None
            assert settings_module.LANGSMITH["tracing"] is False
        finally:
            monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
            monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
            importlib.reload(settings_module)

    def test_api_key_is_stripped(self, monkeypatch):
        monkeypatch.setenv("LANGSMITH_TRACING", "true")
        monkeypatch.setenv("LANGSMITH_API_KEY", "  test-key  ")

        import importlib

        import demetra.settings as settings_module

        importlib.reload(settings_module)

        try:
            assert settings_module.LANGSMITH["api_key"] == "test-key"
            assert settings_module.LANGSMITH["tracing"] is True
        finally:
            monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
            monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
            importlib.reload(settings_module)

    def test_in_process_tracing_flags_forced_off_without_a_key(self, monkeypatch):
        monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)

        import importlib
        import os

        import demetra.settings as settings_module

        importlib.reload(settings_module)

        try:
            assert os.environ["LANGSMITH_TRACING"] == "false"
            assert os.environ["LANGSMITH_TRACING_V2"] == "false"
            assert os.environ["LANGCHAIN_TRACING_V2"] == "false"
        finally:
            importlib.reload(settings_module)

    def test_in_process_tracing_flags_left_alone_when_tracing_enabled(self, monkeypatch):
        monkeypatch.setenv("LANGSMITH_TRACING", "true")
        monkeypatch.setenv("LANGSMITH_API_KEY", "test-key")
        monkeypatch.setenv("LANGSMITH_TRACING_V2", "sentinel")

        import importlib
        import os

        import demetra.settings as settings_module

        importlib.reload(settings_module)

        try:
            assert os.environ["LANGSMITH_TRACING"] == "true"
            assert os.environ["LANGSMITH_TRACING_V2"] == "sentinel"
        finally:
            monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
            monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
            monkeypatch.delenv("LANGSMITH_TRACING_V2", raising=False)
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
