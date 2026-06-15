import inspect

from demetra.services.github import create_pull_request, extract_pr_link


class TestGitHubModuleImports:
    def test_create_pull_request_import(self):
        assert callable(create_pull_request)

    def test_extract_pr_link_import(self):
        assert callable(extract_pr_link)


class TestCreatePullRequestFunction:
    def test_create_pull_request_accepts_required_parameters(self):
        sig = inspect.signature(create_pull_request)
        params = list(sig.parameters.keys())

        assert "target_path" in params
        assert "branch_name" in params
        assert "title" in params


class TestExtractPrLink:
    def test_extracts_url_from_stdout(self):
        stdout = "https://github.com/owner/repo/pull/42\n"
        result = extract_pr_link(stdout)
        assert result == "https://github.com/owner/repo/pull/42"

    def test_returns_none_when_no_url(self):
        result = extract_pr_link("Pull request created successfully\n")
        assert result is None

    def test_returns_first_match_when_multiple_urls(self):
        stdout = "https://github.com/owner/repo/pull/1\nsome output\nhttps://github.com/owner/repo/pull/2\n"
        result = extract_pr_link(stdout)
        assert result == "https://github.com/owner/repo/pull/1"

    def test_handles_empty_string(self):
        result = extract_pr_link("")
        assert result is None

    def test_handles_url_without_newline(self):
        result = extract_pr_link("https://github.com/owner/repo/pull/123")
        assert result == "https://github.com/owner/repo/pull/123"
