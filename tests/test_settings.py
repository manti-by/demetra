from pathlib import Path


class TestSettings:
    def test_home_path_points_to_home(self):
        from demetra import settings

        assert settings.HOME_PATH == Path.home()

    def test_linear_api_url_is_correct(self):
        from demetra import settings

        assert settings.LINEAR["api_url"] == "https://api.linear.app/graphql"

    def test_projects_path_uses_env_or_default(self):
        from demetra import settings

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
        from demetra import settings

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
