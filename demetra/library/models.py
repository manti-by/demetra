from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from slugify import slugify


StepType = Literal[
    "initial", "plan", "build", "review", "lint", "test", "push", "completed", "failed", "awaiting_input"
]


@dataclass
class LinearTask:
    id: str
    identifier: str
    title: str
    description: str
    priority: int
    created_at: str
    state: str | None = None
    project_name: str | None = None
    project_id: str | None = None
    user_id: str | None = None
    comments: list[str] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)
    url: str | None = None

    @property
    def full_title(self) -> str:
        """Return the identifier and title combined into a single display string.

        Returns:
            str: The stripped identifier and title separated by a colon,
                e.g. ``"DEMETRA-123: Add auth"``.
        """
        return f"{self.identifier.strip()}: {self.title.strip()}"

    @property
    def text(self) -> str:
        """Return the task body formatted for LLM consumption.

        Includes the title and description, and appends any comments when
        present.

        Returns:
            str: The prompt-ready task text, optionally with comments.
        """
        if self.comments:
            return f"{self.title.strip()}\n({self.description.strip()})\n\nComments:\n{'\n'.join(self.comments)}"
        return f"{self.title.strip()}\n({self.description.strip()})"

    @property
    def slug(self) -> str:
        """Return a URL-friendly slug derived from the identifier and title.

        Returns:
            str: A slugified string, e.g. ``"demetra-123-add-auth"``.
        """
        return slugify(f"{self.identifier.strip()}-{self.title.strip()}")


@dataclass
class TokenUsage:
    input: int = 0
    output: int = 0
    reasoning: int = 0
    cache_read: int = 0
    cache_write: int = 0
    context: int | None = None

    @property
    def total(self) -> int:
        """Return the sum of all recorded token counts.

        Returns:
            int: Total tokens across input, output, reasoning, cache reads and
                cache writes.
        """
        return self.input + self.output + self.reasoning + self.cache_read + self.cache_write


@dataclass
class SessionHistory:
    id: str
    session_id: str
    step: str
    created_at: str
    length: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    reasoning_tokens: int | None = None
    cache_read_tokens: int | None = None
    cache_write_tokens: int | None = None
    context_tokens: int | None = None
    model: str | None = None


@dataclass
class Session:
    task_id: str
    build_plan: str
    posted_to_linear: bool
    created_at: str
    updated_at: str
    step: StepType = "initial"
    name: str | None = None
    session_id: str | None = None
    project_id: str | None = None
    user_id: str | None = None
    run_attempts: int = 0
    listener_attempts: int = 0
    pr_link: str | None = None
    linear_link: str | None = None


EnvironmentType = Literal["text", "encrypted"]
ENCRYPTED_VALUE_MASK = "********"


@dataclass
class Environment:
    project_id: str
    key: str
    value: str
    type: EnvironmentType = "text"


@dataclass
class ProjectEnvironmentUpsert:
    value: str
    type: EnvironmentType = "text"


@dataclass
class ProjectEnvironmentEntry:
    id: str
    project_id: str
    key: str
    value: str
    type: EnvironmentType = "text"


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
    _environment: dict[str, str] | None = None

    @property
    def environment(self) -> dict[str, str]:
        """Return the cached environment variables for the project.

        Returns:
            dict[str, str]: The environment mapping, or an empty dict when no
                environment has been loaded yet.
        """
        if self._environment is None:
            return {}
        return self._environment

    @environment.setter
    def environment(self, value: dict[str, str]) -> None:
        """Set the cached environment variables for the project.

        Args:
            value: The environment mapping to cache.
        """
        self._environment = value


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
    plan_loop: bool = False

    @property
    def session_id(self) -> str | None:
        """Return the linked session id when a session is present.

        Returns:
            str | None: The session id, or None when the context has no
                session.
        """
        return self.session.session_id if self.session is not None else None

    @property
    def build_plan(self) -> str | None:
        """Return the build plan when a session is present.

        Returns:
            str | None: The session build plan, or None when the context has
                no session.
        """
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
    avatar_url: str | None = None


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
    github_username: str | None = None
    email: str | None = None
    avatar_url: str | None = None
    role: str = "user"


@dataclass
class SignupRequest:
    email: str
    password: str


@dataclass
class LoginRequest:
    email: str
    password: str


@dataclass
class UserKeysUpdateRequest:
    keys: dict
