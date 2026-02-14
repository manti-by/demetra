from demetra.models import LinearIssue


class TestModels:
    def test_linear_issue_text_without_comments(self):
        issue = LinearIssue(
            id="123",
            identifier="DEMETRA-1",
            title="Test Issue",
            description="Test description",
            priority="1",
            created_at="2024-01-01",
            branch_name="feature/test",
        )
        text = issue.text

        assert "Test Issue" in text
        assert "Test description" in text
        assert "Comments:" not in text

    def test_linear_issue_text_with_comments(self):
        issue = LinearIssue(
            id="123",
            identifier="DEMETRA-1",
            title="Test Issue",
            description="Test description",
            priority="1",
            created_at="2024-01-01",
            branch_name="feature/test",
            comments=["Comment 1", "Comment 2"],
        )
        text = issue.text

        assert "Test Issue" in text
        assert "Comments:" in text
        assert "Comment 1" in text
        assert "Comment 2" in text

    def test_linear_issue_slug_generates_correctly(self):
        issue = LinearIssue(
            id="123",
            identifier="DEMETRA-1",
            title="Add user authentication",
            description="",
            priority="1",
            created_at="2024-01-01",
            branch_name="feature/test",
        )
        slug = issue.slug

        assert "demetra-1" in slug.lower()
        assert "add-user-authentication" in slug.lower()

    def test_linear_issue_default_comments_is_empty_list(self):
        issue = LinearIssue(
            id="123",
            identifier="DEMETRA-1",
            title="Test",
            description="",
            priority="1",
            created_at="2024-01-01",
            branch_name="test",
        )
        assert issue.comments == []

    def test_linear_issue_fields_are_accessible(self):
        issue = LinearIssue(
            id="issue-id-123",
            identifier="DEMETRA-42",
            title="My Task",
            description="Task description here",
            priority="2",
            created_at="2024-06-15",
            branch_name="feature/my-task",
            comments=["Note 1"],
        )

        assert issue.id == "issue-id-123"
        assert issue.identifier == "DEMETRA-42"
        assert issue.title == "My Task"
        assert issue.description == "Task description here"
        assert issue.priority == "2"
        assert issue.created_at == "2024-06-15"
        assert issue.branch_name == "feature/my-task"
        assert issue.comments == ["Note 1"]
