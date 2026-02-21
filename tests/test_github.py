class TestGitHubModuleImports:
    def test_create_pull_request_import(self):
        from demetra.services.github import create_pull_request

        assert callable(create_pull_request)


class TestCreatePullRequestFunction:
    def test_create_pull_request_accepts_required_parameters(self):
        import inspect

        from demetra.services.github import create_pull_request

        sig = inspect.signature(create_pull_request)
        params = list(sig.parameters.keys())

        assert "target_path" in params
        assert "branch_name" in params
        assert "title" in params
