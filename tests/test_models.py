from pathlib import Path

from faker import Faker

from demetra.library.models import Environment, LinearTask, Project, SessionHistory


fake = Faker()


class TestModels:
    def test_linear_issue_text_without_comments(self, linear_task: LinearTask):
        text = linear_task.text

        assert linear_task.title in text
        assert linear_task.description in text
        assert "Comments:" not in text

    def test_linear_issue_text_with_comments(self, linear_task: LinearTask):
        linear_task.comments = [fake.sentence(), fake.sentence()]
        text = linear_task.text

        assert linear_task.title in text
        assert "Comments:" in text
        assert linear_task.comments[0] in text
        assert linear_task.comments[1] in text

    def test_linear_issue_slug_generates_correctly(self, linear_task: LinearTask):
        slug = linear_task.slug

        assert linear_task.identifier.lower() in slug.lower()
        title_for_slug = linear_task.title.lower().rstrip(".").replace(" ", "-")
        assert title_for_slug in slug.lower()

    def test_linear_issue_default_comments_is_empty_list(self, linear_task: LinearTask):
        assert linear_task.comments == []

    def test_linear_issue_default_labels_is_empty_list(self, linear_task: LinearTask):
        assert linear_task.labels == []

    def test_linear_issue_labels_stores_names_only(self, linear_task: LinearTask):
        linear_task.labels = ["bug", "frontend", "high-priority"]
        assert len(linear_task.labels) == 3
        assert "bug" in linear_task.labels
        assert "frontend" in linear_task.labels
        assert all(isinstance(label, str) for label in linear_task.labels)

    def test_linear_issue_fields_are_accessible(self, linear_task: LinearTask):
        linear_task.comments = [fake.sentence()]
        linear_task.labels = ["bug"]

        assert linear_task.id
        assert linear_task.identifier
        assert linear_task.title
        assert linear_task.description
        assert linear_task.priority
        assert linear_task.created_at
        assert linear_task.comments
        assert linear_task.labels


class TestEnvironment:
    def test_environment_dataclass_has_required_fields(self):
        env = Environment(project_id="proj-123", key="MY_KEY", value="my_value")

        assert env.project_id == "proj-123"
        assert env.key == "MY_KEY"
        assert env.value == "my_value"


class TestProjectEnvironment:
    def test_project_environment_returns_empty_dict_by_default(self):
        project = Project(
            id="proj-1",
            user_id="usr-1",
            linear_project_id=None,
            name="test-project",
            state="active",
            repository_url="https://github.com/owner/repo",
            repository_name="repo",
            repository_owner="owner",
            local_path=Path("/tmp/test"),
            created_at="2026-01-01T00:00:00",
            updated_at="2026-01-01T00:00:00",
        )

        assert project.environment == {}

    def test_project_environment_returns_set_values(self):
        project = Project(
            id="proj-1",
            user_id="usr-1",
            linear_project_id=None,
            name="test-project",
            state="active",
            repository_url="https://github.com/owner/repo",
            repository_name="repo",
            repository_owner="owner",
            local_path=Path("/tmp/test"),
            created_at="2026-01-01T00:00:00",
            updated_at="2026-01-01T00:00:00",
        )
        project.environment = {"API_KEY": "secret123", "DB_URL": "postgres://localhost"}

        assert project.environment == {"API_KEY": "secret123", "DB_URL": "postgres://localhost"}

    def test_project_environment_is_cached(self):
        project = Project(
            id="proj-1",
            user_id="usr-1",
            linear_project_id=None,
            name="test-project",
            state="active",
            repository_url="https://github.com/owner/repo",
            repository_name="repo",
            repository_owner="owner",
            local_path=Path("/tmp/test"),
            created_at="2026-01-01T00:00:00",
            updated_at="2026-01-01T00:00:00",
        )
        project.environment = {"KEY": "value1"}
        env1 = project.environment
        env2 = project.environment

        assert env1 is env2
        assert env1 == {"KEY": "value1"}


class TestSessionHistory:
    def test_session_history_dataclass_has_required_fields(self):
        history = SessionHistory(
            id="hist-001",
            session_id="ses_abc123",
            step="build",
            length=12345,
            created_at="2026-06-30T12:00:00+00:00",
        )
        assert history.id == "hist-001"
        assert history.session_id == "ses_abc123"
        assert history.step == "build"
        assert history.length == 12345
        assert history.created_at == "2026-06-30T12:00:00+00:00"
        assert isinstance(history.length, int)

    def test_session_history_default_length_is_none(self):
        history = SessionHistory(
            id="hist-002",
            session_id="ses_def456",
            step="plan",
            created_at="2026-06-30T12:00:00+00:00",
        )
        assert history.length is None
