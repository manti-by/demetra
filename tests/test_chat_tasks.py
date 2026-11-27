from demetra.library.models import ChatMessage
from demetra.services.chat.tasks import compile_question_answers


def _message(message_id: str, **overrides: object) -> ChatMessage:
    values: dict[str, object] = {
        "id": message_id,
        "task_id": "CH-1",
        "parent_id": None,
        "related_id": None,
        "source": "chat",
        "external_id": None,
        "author_id": None,
        "author_name": None,
        "is_system": False,
        "is_added_to_context": False,
        "kind": "message",
        "body": "body",
        "created_at": "2026-11-27T10:00:00Z",
    }
    values.update(overrides)
    return ChatMessage(**values)  # type: ignore[arg-type]


class TestCompileQuestionAnswers:
    def test_pairs_questions_with_answers_in_thread_order(self):
        messages = [
            _message("q1", kind="question", body="## Question:\nUse Postgres?"),
            _message("q2", kind="question", body="## Question:\nWhich port?"),
            _message("a2", kind="answer", related_id="q2", body="5432"),
            _message("a1", kind="answer", related_id="q1", body="Yes"),
        ]

        block, ids = compile_question_answers(messages)

        assert block == ("1. Question: Use Postgres?\n   Answer: Yes\n2. Question: Which port?\n   Answer: 5432")
        assert ids == ["q1", "a1", "q2", "a2"]

    def test_keeps_multiple_answers_for_one_question(self):
        messages = [
            _message("q1", kind="question", body="Question: Pick one"),
            _message("a1", kind="answer", related_id="q1", body="First"),
            _message("a2", kind="answer", related_id="q1", body="Second"),
        ]

        block, ids = compile_question_answers(messages)

        assert block == "1. Question: Question: Pick one\n   Answer: First\n   Answer: Second"
        assert ids == ["q1", "a1", "a2"]

    def test_skips_consumed_answers_and_unanswered_questions(self):
        messages = [
            _message("q1", kind="question", body="## Question:\nDone?", is_added_to_context=True),
            _message("a1", kind="answer", related_id="q1", body="Yes", is_added_to_context=True),
            _message("q2", kind="question", body="## Question:\nOpen?"),
            _message("q3", kind="question", body="## Question:\nAlso open?"),
            _message("a3", kind="answer", related_id="q3", body="Later"),
        ]

        block, ids = compile_question_answers(messages)

        assert block == "1. Question: Also open?\n   Answer: Later"
        assert ids == ["q3", "a3"]

    def test_ignores_answers_without_a_question_on_the_same_thread(self):
        messages = [
            _message("a1", kind="answer", related_id="missing", body="Orphan"),
            _message("m1", kind="message", body="Ordinary reply"),
        ]

        assert compile_question_answers(messages) == ("", [])
