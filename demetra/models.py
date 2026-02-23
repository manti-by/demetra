from dataclasses import dataclass, field
from pathlib import Path

from slugify import slugify


@dataclass
class LinearIssue:
    id: str
    identifier: str
    title: str
    description: str
    priority: str
    created_at: str
    branch_name: str
    comments: list[str] = field(default_factory=list)

    @property
    def full_title(self) -> str:
        return f"{self.identifier}: {self.title}"

    @property
    def text(self) -> str:
        if self.comments:
            return f"{self.title}\n({self.description})\n\nComments:\n{'\n'.join(self.comments)}"
        return f"{self.title}\n({self.description})"

    @property
    def slug(self) -> str:
        return slugify(f"{self.identifier}-{self.title}")


@dataclass
class Session:
    task_id: str
    session_id: str
    created_at: str
    updated_at: str


@dataclass
class BuildPlan:
    task_id: str
    plan_content: str
    created_at: str
    posted_to_linear: bool


@dataclass
class Context:
    project_name: str
    auto_mode: bool
    linear_task: LinearIssue
    branch_name: str
    project_path: Path
    worktree_path: Path
    session: Session | None
    build_plan: BuildPlan | None = None

    @property
    def session_id(self) -> str | None:
        return self.session.session_id if self.session is not None else None
