from pathlib import Path

import pytest

from demetra import settings
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

    def test_max_plan_attempts_default(self, monkeypatch):
        monkeypatch.delenv("MAX_PLAN_ATTEMPTS", raising=False)
        import importlib

        import demetra.settings as settings_module

        importlib.reload(settings_module)

        assert settings_module.MAX_PLAN_ATTEMPTS == 30

    def test_max_plan_attempts_env_override(self, monkeypatch):
        monkeypatch.setenv("MAX_PLAN_ATTEMPTS", "5")
        import importlib

        import demetra.settings as settings_module

        importlib.reload(settings_module)

        try:
            assert settings_module.MAX_PLAN_ATTEMPTS == 5
        finally:
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
            assert "PATH" in settings_module.OS_ENV_ALLOWLIST
            assert "HOME" in settings_module.OS_ENV_ALLOWLIST
            assert "VIRTUAL_ENV" in settings_module.OS_ENV_ALLOWLIST
            assert "PWD" in settings_module.OS_ENV_ALLOWLIST
            assert "GITHUB_TOKEN" not in settings_module.OS_ENV_ALLOWLIST
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
                assert key in settings_module.OS_ENV_ALLOWLIST
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
            assert settings_module.DEMETRA_SECRET_KEY == "fallback-secret"
        finally:
            monkeypatch.delenv("SECRET_KEY", raising=False)
            importlib.reload(settings_module)

    def test_demetra_secret_key_env_override(self, monkeypatch):
        monkeypatch.setenv("DEMETRA_SECRET_KEY", "dedicated-secret")

        import importlib

        import demetra.settings as settings_module

        importlib.reload(settings_module)

        try:
            assert settings_module.DEMETRA_SECRET_KEY == "dedicated-secret"
        finally:
            monkeypatch.delenv("DEMETRA_SECRET_KEY", raising=False)
            importlib.reload(settings_module)

    def test_wiki_budget_falls_back_to_legacy_env_names(self, monkeypatch):
        monkeypatch.delenv("WIKI_LLM_BUDGET_FILES", raising=False)
        monkeypatch.delenv("WIKI_LLM_BUDGET_LINES", raising=False)
        monkeypatch.setenv("WIKI_GROQ_BUDGET_FILES", "12")
        monkeypatch.setenv("WIKI_GROQ_BUDGET_LINES", "300")

        import importlib

        import demetra.settings as settings_module

        importlib.reload(settings_module)

        try:
            assert settings_module.WIKI_LLM_BUDGET_FILES == 12
            assert settings_module.WIKI_LLM_BUDGET_LINES == 300
        finally:
            monkeypatch.delenv("WIKI_GROQ_BUDGET_FILES", raising=False)
            monkeypatch.delenv("WIKI_GROQ_BUDGET_LINES", raising=False)
            importlib.reload(settings_module)

    def test_wiki_budget_new_names_take_precedence(self, monkeypatch):
        monkeypatch.setenv("WIKI_LLM_BUDGET_FILES", "5")
        monkeypatch.setenv("WIKI_GROQ_BUDGET_FILES", "12")

        import importlib

        import demetra.settings as settings_module

        importlib.reload(settings_module)

        try:
            assert settings_module.WIKI_LLM_BUDGET_FILES == 5
        finally:
            monkeypatch.delenv("WIKI_LLM_BUDGET_FILES", raising=False)
            monkeypatch.delenv("WIKI_GROQ_BUDGET_FILES", raising=False)
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

    @pytest.mark.parametrize(
        ("url", "expected"),
        [
            ("https://openrouter.ai/api/v1", "https://openrouter.ai/api/v1"),
            ("https://custom.example/v1", "https://custom.example/v1"),
            ("http://localhost:8000/v1", "http://localhost:8000/v1"),
            ("http://127.0.0.1:8000/v1", "http://127.0.0.1:8000/v1"),
            ("http://[::1]:8000/v1", "http://[::1]:8000/v1"),
        ],
    )
    def test_validate_llm_base_url_accepts_valid(self, url, expected):
        assert settings.validate_llm_base_url(url) == expected

    @pytest.mark.parametrize(
        "url",
        [
            None,
            "",
            "   ",
            "not a url",
            "openrouter.ai/api/v1",
            "https://",
            "ftp://host/v1",
            "http://evil.example/v1",
            "https://user:pass@evil.example/v1",
        ],
    )
    def test_validate_llm_base_url_rejects_invalid(self, url):
        with pytest.raises(SettingsError):
            settings.validate_llm_base_url(url)

    def test_is_loopback_host(self):
        assert settings.is_loopback_host("localhost")
        assert settings.is_loopback_host("127.0.0.1")
        assert settings.is_loopback_host("127.5.5.5")
        assert settings.is_loopback_host("::1")
        assert not settings.is_loopback_host("evil.example")
