from dataclasses import dataclass, field
from typing import Optional

@dataclass
class Context:
    project_name: str
    issue_id: Optional[str] = None
    agent_state: dict = field(default_factory=dict)
