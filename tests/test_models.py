from faker import Faker

from demetra.library.models import LinearTask


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

    def test_linear_issue_fields_are_accessible(self, linear_task: LinearTask):
        linear_task.comments = [fake.sentence()]

        assert linear_task.id
        assert linear_task.identifier
        assert linear_task.title
        assert linear_task.description
        assert linear_task.priority
        assert linear_task.created_at
        assert linear_task.branch_name
        assert linear_task.comments
