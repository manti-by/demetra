import inspect

from demetra.services.git import (
    git_branch_delete,
    git_cleanup,
    git_commit,
    git_push,
    git_worktree_create,
    git_worktree_remove,
)


class TestGitModuleImports:
    def test_git_worktree_create_import(self):
        assert callable(git_worktree_create)

    def test_git_worktree_remove_import(self):
        assert callable(git_worktree_remove)

    def test_git_commit_import(self):
        assert callable(git_commit)

    def test_git_push_import(self):
        assert callable(git_push)

    def test_git_branch_delete_import(self):
        assert callable(git_branch_delete)

    def test_git_cleanup_import(self):
        assert callable(git_cleanup)


class TestGitCleanupFunction:
    def test_git_cleanup_accepts_required_parameters(self):
        sig = inspect.signature(git_cleanup)
        params = list(sig.parameters.keys())

        assert "context" in params
        assert "is_success" in params

    def test_git_cleanup_success_is_keyword_only(self):
        sig = inspect.signature(git_cleanup)
        success_param = sig.parameters.get("is_success")

        assert success_param is not None
        assert success_param.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD
