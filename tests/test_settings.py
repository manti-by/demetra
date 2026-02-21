from pathlib import Path


class TestSettings:
    def test_home_path_points_to_home(self):
        from demetra import settings

        assert settings.HOME_PATH == Path.home()

    def test_linear_api_url_is_correct(self):
        from demetra import settings

        assert settings.LINEAR_API_URL == "https://api.linear.app/graphql"

    def test_projects_path_uses_env_or_default(self):
        from demetra import settings

        assert "www" in str(settings.PROJECTS_PATH)

    def test_opencode_defaults(self):
        from demetra import settings

        assert ".opencode" in str(settings.OPENCODE_PATH)
        assert "opencode" in settings.OPENCODE_MODEL

    def test_git_worktree_path_default(self):
        from demetra import settings

        assert ".demetra/worktrees" in str(settings.GIT_WORKTREE_PATH)

    def test_settings_can_be_overridden_via_env(self, monkeypatch):
        monkeypatch.setenv("PROJECTS_PATH", "/custom/projects")
        monkeypatch.setenv("LINEAR_API_KEY", "test-key")
        monkeypatch.setenv("LINEAR_TEAM_ID", "test-team")

        import importlib

        import demetra.settings as settings_module

        importlib.reload(settings_module)

        try:
            assert "/custom/projects" in str(settings_module.PROJECTS_PATH)
            assert settings_module.LINEAR_API_KEY == "test-key"
            assert settings_module.LINEAR_TEAM_ID == "test-team"
        finally:
            # Restore original module state for other tests
            monkeypatch.delenv("PROJECTS_PATH", raising=False)
            monkeypatch.delenv("LINEAR_API_KEY", raising=False)
            monkeypatch.delenv("LINEAR_TEAM_ID", raising=False)
            importlib.reload(settings_module)
