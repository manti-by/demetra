from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from faker import Faker


fake = Faker()


@pytest.fixture
def faker():
    return fake


@pytest.fixture
def linear_team_id() -> str:
    return f"team-{uuid4().hex[:8]}"


@pytest.fixture
def linear_state_id() -> str:
    return f"state-{uuid4().hex[:8]}"


@pytest.fixture
def linear_issue_id() -> str:
    return f"issue-{uuid4().hex[:8]}"


@pytest.fixture
def linear_identifier() -> str:
    return f"MNT-{fake.random_int(min=1, max=999)}"


@pytest.fixture
def linear_graphql_response_success(linear_issue_id: str, linear_identifier: str) -> dict:
    return {
        "data": {
            "issueCreate": {
                "success": True,
                "issue": {
                    "id": linear_issue_id,
                    "identifier": linear_identifier,
                    "title": fake.sentence(nb_words=4),
                },
            }
        }
    }


@pytest.fixture
def linear_graphql_response_failure() -> dict:
    return {
        "data": {
            "issueCreate": {
                "success": False,
            }
        }
    }


@pytest.fixture
def groq_processed_data() -> dict:
    return {
        "title": fake.sentence(nb_words=4),
        "description": fake.paragraph(nb_sentences=3),
        "technical_requirements": fake.paragraph(nb_sentences=2),
        "acceptance_criteria": fake.paragraph(nb_sentences=2),
        "project_name": "demetra",
    }


@pytest.fixture
def linear_ticket_data(linear_issue_id: str, linear_identifier: str) -> dict:
    return {
        "ticket_id": linear_issue_id,
        "identifier": linear_identifier,
        "title": fake.sentence(nb_words=4),
    }


@pytest.fixture
async def mock_graphql_request(
    linear_graphql_response_success: dict,
) -> AsyncGenerator[AsyncMock]:
    with patch(
        "demetra.services.linear.graphql_request",
        new_callable=AsyncMock,
    ) as mock:
        mock.return_value = linear_graphql_response_success
        yield mock


@pytest.fixture
async def mock_groq(groq_processed_data: dict) -> AsyncGenerator[AsyncMock]:
    with patch(
        "demetra.api.process_text_with_groq",
        new_callable=AsyncMock,
    ) as mock:
        mock.return_value = groq_processed_data
        yield mock


@pytest.fixture
async def mock_create_linear_ticket(
    linear_ticket_data: dict,
) -> AsyncGenerator[AsyncMock]:
    with patch(
        "demetra.api.create_linear_ticket",
        new_callable=AsyncMock,
    ) as mock:
        mock.return_value = linear_ticket_data
        yield mock


@pytest.fixture
def linear_settings(linear_team_id: str, linear_state_id: str):
    return {
        "team_id": linear_team_id,
        "states": {
            "todo": linear_state_id,
        },
    }


@pytest.fixture
async def mock_linear_settings(linear_settings: dict):
    with patch("demetra.services.linear.LINEAR", linear_settings):
        yield


@pytest.fixture
def linear_task_data() -> dict:
    return {
        "id": f"issue-{uuid4().hex[:8]}",
        "identifier": f"MNT-{fake.random_int(min=1, max=999)}",
        "title": fake.sentence(nb_words=4),
        "description": fake.paragraph(nb_sentences=2),
        "priority": fake.random_int(min=1, max=4),
        "createdAt": fake.date_time().isoformat(),
        "branchName": f"feature/{fake.slug()}",
        "project": {"name": fake.word()},
    }


@pytest.fixture
def linear_task_data_demetra() -> dict:
    return {
        "id": f"issue-{uuid4().hex[:8]}",
        "identifier": f"MNT-{fake.random_int(min=1, max=999)}",
        "title": fake.sentence(nb_words=4),
        "description": fake.paragraph(nb_sentences=2),
        "priority": fake.random_int(min=1, max=4),
        "createdAt": fake.date_time().isoformat(),
        "branchName": f"feature/{fake.slug()}",
        "project": {"name": "demetra"},
    }


@pytest.fixture
def linear_task(linear_task_data: dict):
    from demetra.library.models import LinearTask

    return LinearTask(
        id=linear_task_data["id"],
        identifier=linear_task_data["identifier"],
        title=linear_task_data["title"],
        description=linear_task_data["description"],
        priority=linear_task_data["priority"],
        created_at=linear_task_data["createdAt"],
        branch_name=linear_task_data["branchName"],
        project_name=linear_task_data["project"]["name"],
    )


@pytest.fixture
def graphql_todo_issues_response(linear_task_data: dict) -> dict:
    return {
        "data": {
            "team": {
                "states": {
                    "nodes": [
                        {
                            "name": "Todo",
                            "issues": {
                                "nodes": [linear_task_data],
                            },
                        }
                    ]
                }
            }
        }
    }


@pytest.fixture
def graphql_todo_issues_response_demetra(linear_task_data_demetra: dict) -> dict:
    return {
        "data": {
            "team": {
                "states": {
                    "nodes": [
                        {
                            "name": "Todo",
                            "issues": {
                                "nodes": [linear_task_data_demetra],
                            },
                        }
                    ]
                }
            }
        }
    }


@pytest.fixture
def graphql_todo_issues_multiple_response() -> dict:
    tasks = []
    for _ in range(2):
        tasks.append(
            {
                "id": f"issue-{uuid4().hex[:8]}",
                "identifier": f"MNT-{fake.random_int(min=1, max=999)}",
                "title": fake.sentence(nb_words=4),
                "description": fake.paragraph(nb_sentences=2),
                "priority": fake.random_int(min=1, max=4),
                "createdAt": fake.date_time().isoformat(),
                "branchName": f"feature/{fake.slug()}",
                "project": {"name": fake.word()},
            }
        )
    return {
        "data": {
            "team": {
                "states": {
                    "nodes": [
                        {
                            "name": "Todo",
                            "issues": {
                                "nodes": tasks,
                            },
                        }
                    ]
                }
            }
        }
    }


@pytest.fixture
def graphql_todo_issues_multiple_response_demetra() -> dict:
    tasks = []
    for _ in range(2):
        tasks.append(
            {
                "id": f"issue-{uuid4().hex[:8]}",
                "identifier": f"MNT-{fake.random_int(min=1, max=999)}",
                "title": fake.sentence(nb_words=4),
                "description": fake.paragraph(nb_sentences=2),
                "priority": fake.random_int(min=1, max=4),
                "createdAt": fake.date_time().isoformat(),
                "branchName": f"feature/{fake.slug()}",
                "project": {"name": "demetra"},
            }
        )
    return {
        "data": {
            "team": {
                "states": {
                    "nodes": [
                        {
                            "name": "Todo",
                            "issues": {
                                "nodes": tasks,
                            },
                        }
                    ]
                }
            }
        }
    }


@pytest.fixture
def graphql_empty_response() -> dict:
    return {"data": {"team": {"states": {"nodes": []}}}}


@pytest.fixture
def graphql_update_success_response() -> dict:
    return {
        "data": {
            "issueUpdate": {
                "success": True,
                "issue": {
                    "id": f"issue-{uuid4().hex[:8]}",
                    "state": {"id": f"state-{uuid4().hex[:8]}", "name": fake.word()},
                },
            }
        }
    }


@pytest.fixture
def graphql_update_failure_response() -> dict:
    return {
        "data": {
            "issueUpdate": {
                "success": False,
            }
        }
    }


@pytest.fixture
def graphql_comment_success_response() -> dict:
    return {
        "data": {
            "commentCreate": {
                "success": True,
                "comment": {
                    "id": f"comment-{uuid4().hex[:8]}",
                    "body": fake.sentence(),
                },
            }
        }
    }


@pytest.fixture
def graphql_comment_failure_response() -> dict:
    return {
        "data": {
            "commentCreate": {
                "success": False,
            }
        }
    }


@pytest.fixture
def db_task_id() -> str:
    return f"TASK-{fake.random_int(min=100, max=999)}"


@pytest.fixture
def db_session_id() -> str:
    return f"session-{uuid4().hex[:8]}"


@pytest.fixture
def db_build_plan() -> str:
    return fake.text(max_nb_chars=100)
