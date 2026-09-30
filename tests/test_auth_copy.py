from pathlib import Path

import pytest

from demetra.services.auth.copy import copy_auth_from_parent


class TestCopyAuthFromParent:
    @pytest.mark.asyncio
    async def test_excludes_claude_projects_directory(self, tmp_path, monkeypatch):
        parent_home = tmp_path / "parent"
        current_home = tmp_path / "current"
        parent_home.mkdir()
        current_home.mkdir()
        monkeypatch.setattr(Path, "home", lambda: current_home)

        claude_dir = parent_home / ".claude"
        (claude_dir / "projects" / "some-session").mkdir(parents=True)
        (claude_dir / "projects" / "some-session" / "transcript.jsonl").write_text("{}\n")
        (claude_dir / "settings.json").write_text('{"apiKeyHelper": "x"}')

        await copy_auth_from_parent(parent_home=parent_home)

        assert (current_home / ".claude" / "settings.json").read_text() == '{"apiKeyHelper": "x"}'
        assert not (current_home / ".claude" / "projects").exists()

    @pytest.mark.asyncio
    async def test_copies_opencode_and_gh_config_unaffected(self, tmp_path, monkeypatch):
        parent_home = tmp_path / "parent"
        current_home = tmp_path / "current"
        parent_home.mkdir()
        current_home.mkdir()
        monkeypatch.setattr(Path, "home", lambda: current_home)

        opencode_dir = parent_home / ".config" / "opencode"
        opencode_dir.mkdir(parents=True)
        (opencode_dir / "auth.json").write_text('{"token": "x"}')

        gh_dir = parent_home / ".config" / "gh"
        gh_dir.mkdir(parents=True)
        (gh_dir / "hosts.yml").write_text("github.com:\n  oauth_token: x\n")

        await copy_auth_from_parent(parent_home=parent_home)

        assert (current_home / ".config" / "opencode" / "auth.json").read_text() == '{"token": "x"}'
        assert (current_home / ".config" / "gh" / "hosts.yml").exists()

    @pytest.mark.asyncio
    async def test_no_parent_home_is_a_no_op(self, tmp_path, monkeypatch):
        current_home = tmp_path / "current"
        current_home.mkdir()
        monkeypatch.setattr(Path, "home", lambda: current_home)

        await copy_auth_from_parent(parent_home=None)

        assert list(current_home.iterdir()) == []

    @pytest.mark.asyncio
    async def test_same_parent_and_current_home_is_skipped(self, tmp_path, monkeypatch):
        home = tmp_path / "home"
        home.mkdir()
        (home / ".claude").mkdir()
        monkeypatch.setattr(Path, "home", lambda: home)

        await copy_auth_from_parent(parent_home=home)

        # No copy-onto-itself error, and nothing new was created.
        assert list((home / ".claude").iterdir()) == []
