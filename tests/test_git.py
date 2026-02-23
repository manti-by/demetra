class TestGitModuleImports:
    def test_git_worktree_create_import(self):
        from demetra.services.git import git_worktree_create

        assert callable(git_worktree_create)

    def test_git_worktree_remove_import(self):
        from demetra.services.git import git_worktree_remove

        assert callable(git_worktree_remove)

    def test_git_commit_import(self):
        from demetra.services.git import git_commit

        assert callable(git_commit)

    def test_git_push_import(self):
        from demetra.services.git import git_push

        assert callable(git_push)

    def test_git_branch_delete_import(self):
        from demetra.services.git import git_branch_delete

        assert callable(git_branch_delete)

    def test_git_cleanup_import(self):
        from demetra.services.git import git_cleanup

        assert callable(git_cleanup)


class TestGitCleanupFunction:
    def test_git_cleanup_accepts_required_parameters(self):
        import inspect

        from demetra.services.git import git_cleanup

        sig = inspect.signature(git_cleanup)
        params = list(sig.parameters.keys())

        assert "target_path" in params
        assert "worktree_path" in params
        assert "branch_name" in params
        assert "success" in params

    def test_git_cleanup_success_is_keyword_only(self):
        import inspect

        from demetra.services.git import git_cleanup

        sig = inspect.signature(git_cleanup)
        success_param = sig.parameters.get("success")

        assert success_param is not None
        assert success_param.kind == inspect.Parameter.KEYWORD_ONLY
