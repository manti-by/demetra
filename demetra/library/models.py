from dataclasses import dataclass, field
from pathlib import Path

from slugify import slugify


@dataclass
class LinearTask:
    id: str
    identifier: str
    title: str
    description: str
    priority: str
    created_at: str
    state: str | None = None
    project_name: str | None = None
    project_id: str | None = None
    user_id: str | None = None
    comments: list[str] = field(default_factory=list)

    @property
    def full_title(self) -> str:
        return f"{self.identifier.strip()}: {self.title.strip()}"

    @property
    def text(self) -> str:
        if self.comments:
            return f"{self.title.strip()}\n({self.description.strip()})\n\nComments:\n{'\n'.join(self.comments)}"
        return f"{self.title.strip()}\n({self.description.strip()})"

    @property
    def slug(self) -> str:
        return slugify(f"{self.identifier.strip()}-{self.title.strip()}")


@dataclass
class Session:
    task_id: str
    build_plan: str
    posted_to_linear: bool
    created_at: str
    updated_at: str
    status: str = "pending"
    session_id: str | None = None
    project_id: str | None = None
    user_id: str | None = None


@dataclass
class Project:
    id: str
    user_id: str | None
    linear_project_id: str | None
    name: str
    state: str
    repository_url: str
    repository_name: str
    repository_owner: str
    local_path: Path
    created_at: str
    updated_at: str


@dataclass
class CreateProject:
    name: str
    repository_url: str
    linear_project_id: str | None = None


@dataclass
class UpdateProject:
    name: str | None = None
    repository_url: str | None = None
    linear_project_id: str | None = None


@dataclass
class Context:
    project: Project
    auto_mode: bool
    linear_task: LinearTask
    branch_name: str
    worktree_path: Path
    session: Session | None

    @property
    def session_id(self) -> str | None:
        return self.session.session_id if self.session is not None else None

    @property
    def build_plan(self) -> str | None:
        return self.session.build_plan if self.session is not None else None


@dataclass
class CreateTicket:
    text: str


@dataclass
class Ticket:
    ticket_id: str
    identifier: str
    title: str


@dataclass
class GitHubUser:
    id: str
    login: str
    email: str | None


@dataclass
class TokenData:
    user_id: str
    exp: int


@dataclass
class AuthResponse:
    token: str
    user: "UserResponse"


@dataclass
class UserResponse:
    id: str
    github_username: str
    email: str | None
    role: str = "user"


@dataclass
class UserKeysUpdateRequest:
    keys: dict
