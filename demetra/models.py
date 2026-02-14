from dataclasses import dataclass


@dataclass
class LinearIssue:
    id: str
    identifier: str
    title: str
    description: str
    priority: str
    state: str
    created_at: str
    branch_name: str
