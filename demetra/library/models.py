import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

from slugify import slugify

from demetra.library.constants import AGENT_HARNESSES, CLAUDE_EFFORT_LEVELS
from demetra.library.exceptions import EnvironmentConfigError
from demetra.library.types import OpenRouterConfig, WaitlistStatus


StepType = Literal[
    "initial",
    "plan",
    "research",
    "build",
    "validate",
    "review",
    "lint",
    "test",
    "wiki",
    "push",
    "completed",
    "failed",
    "awaiting_input",
    "researched",
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
    linear_project_id: str | None = None
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
class ReviewModel:
    model: str
    effort: str | None = None


def parse_review_model(entry: str, harness: str) -> ReviewModel:
    """Parse a single ``model[:effort]`` review model entry.

    OpenCode model names never carry an effort suffix (the harness has no
    effort flag); only Claude entries are split on the trailing ``:effort``.

    Args:
        entry: The raw review model entry, e.g. ``"opus:xhigh"``.
        harness: The active agent harness, ``"opencode"`` or ``"claude"``.

    Returns:
        ReviewModel: The parsed model and optional effort.

    Raises:
        EnvironmentConfigError: When a Claude entry's effort is not a
            recognized effort level.
    """
    entry = entry.strip()
    if harness != "claude" or ":" not in entry:
        return ReviewModel(model=entry)

    model, _, effort = entry.rpartition(":")
    effort = effort.strip() or None
    if effort is not None and effort not in CLAUDE_EFFORT_LEVELS:
        raise EnvironmentConfigError(f"Invalid effort {effort!r} in review model {entry!r}")
    return ReviewModel(model=model.strip(), effort=effort)


@dataclass
class ClaudeResult:
    result: str
    is_error: bool
    session_id: str | None
    usage: TokenUsage | None
    subtype: str = ""
    num_turns: int = 0
    permission_denials: list[str] = field(default_factory=list)


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
    harness: str = "opencode"
    project_id: str | None = None
    user_id: str | None = None
    run_attempts: int = 0
    listener_attempts: int = 0
    pr_link: str | None = None
    linear_link: str | None = None
    research_report: str | None = None


EnvironmentType = Literal["text", "encrypted"]
ENCRYPTED_VALUE_MASK = "********"

EnvironmentScope = Literal["project", "user"]

SENSITIVE_KEY_PATTERN = re.compile(
    r"(?:TOKEN|SECRET|KEY|PASSWORD)$|(?:^|[\W_])(?:TOKEN|SECRET|KEY|PASSWORD)[\W_]", re.IGNORECASE
)


def is_sensitive_key(key: str) -> bool:
    """Return whether an environment key should be treated as sensitive.

    Keys containing the whole words ``TOKEN``, ``SECRET``, ``KEY`` or
    ``PASSWORD`` (case-insensitive) are masked in API responses and the
    React UI, even when stored as plaintext. A keyword matches when it is
    delimited by start/end or a non-alnum character (like ``_``, ``-`` or
    ``.``), or when it closes the key name at end-of-string (so concatenated
    names such as ``STRIPEAPIKEY`` or ``CLIENTPASSWORD`` are flagged too).
    Delimiter matching avoids false positives such as ``KEYBOARD_LAYOUT``,
    ``MONKEY_BUSINESS`` or ``TOKENIZATION`` while still matching
    ``GITHUB_TOKEN``, ``API_KEY`` and ``DB_PASSWORD``.

    Args:
        key: The environment variable name.

    Returns:
        bool: True when the key matches the sensitive-key pattern.
    """
    return SENSITIVE_KEY_PATTERN.search(key) is not None


@dataclass
class Environment:
    key: str
    value: str
    type: EnvironmentType = "text"
    project_id: str | None = None
    user_id: str | None = None
    scope: EnvironmentScope = "project"


@dataclass
class EnvironmentUpsert:
    value: str
    type: EnvironmentType = "text"
    previous_key: str | None = None


@dataclass
class EnvironmentEntry:
    id: str
    key: str
    value: str
    type: EnvironmentType = "text"
    scope: EnvironmentScope = "project"
    project_id: str | None = None
    user_id: str | None = None


@dataclass
class ProjectEnvironmentUpsert:
    value: str
    type: EnvironmentType = "text"
    previous_key: str | None = None


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
    _user_environment: dict[str, str] | None = None

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

    @property
    def user_environment(self) -> dict[str, str]:
        """Return the cached user-shared environment for the project's owner.

        Returns:
            dict[str, str]: The user-shared environment mapping, or an empty
                dict when no environment has been loaded yet.
        """
        if self._user_environment is None:
            return {}
        return self._user_environment

    @user_environment.setter
    def user_environment(self, value: dict[str, str]) -> None:
        """Set the cached user-shared environment for the project's owner.

        Args:
            value: The user-shared environment mapping to cache.
        """
        self._user_environment = value


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


def _settings_default(key: str) -> str | None:
    """Return the ``settings.py`` default for a workflow environment key.

    The settings module is imported lazily so the library layer stays free of
    import-time configuration reads; only a key that misses both the project
    and user-shared env layers reaches this fallback.

    Args:
        key: The environment variable name.

    Returns:
        str | None: The configured default, or None when settings does not
            define the key.
    """
    from demetra.settings import (
        AGENT_HARNESS,
        CLAUDE,
        CLAUDE_DEFAULT_MAX_BUDGET_USD,
        CLAUDE_MAX_BUDGET_USD,
        LINEAR,
        OPENCODE,
        OPENROUTER,
    )

    if key == "OPENROUTER_API_KEY":
        return OPENROUTER["api_key"]
    if key == "OPENROUTER_MODEL":
        return OPENROUTER["model"]
    if key == "OPENROUTER_BASE_URL":
        return OPENROUTER["base_url"]
    if key == "LINEAR_TEAM_ID":
        return LINEAR["team_id"]
    if key == "LINEAR_DEFAULT_STATE_ID":
        return LINEAR["default_state"]
    if key == "AGENT_HARNESS":
        return AGENT_HARNESS
    if key == "OPENCODE_REVIEW_MODELS":
        return ",".join(OPENCODE["review_models"])
    if key == "CLAUDE_REVIEW_MODELS":
        return ",".join(CLAUDE["review_models"])
    if key == "CLAUDE_MAX_BUDGET_USD":
        return str(CLAUDE_DEFAULT_MAX_BUDGET_USD)
    if key.startswith("OPENCODE_") and key.endswith("_MODEL"):
        agent = key[len("OPENCODE_") : -len("_MODEL")].lower()
        opencode_models = {
            "plan": OPENCODE["plan_model"],
            "build": OPENCODE["build_model"],
            "resolve": OPENCODE["resolve_model"],
            "validate": OPENCODE["validate_model"],
            "research": OPENCODE["research_model"],
        }
        return opencode_models.get(agent)
    if key.startswith("CLAUDE_") and key.endswith("_MAX_BUDGET_USD"):
        agent = key[len("CLAUDE_") : -len("_MAX_BUDGET_USD")].lower()
        return str(CLAUDE_MAX_BUDGET_USD.get(agent, CLAUDE_DEFAULT_MAX_BUDGET_USD))
    if key.startswith("CLAUDE_") and key.endswith("_MODEL"):
        agent = key[len("CLAUDE_") : -len("_MODEL")].lower()
        claude_models = {
            "plan": CLAUDE["plan_model"],
            "build": CLAUDE["build_model"],
            "resolve": CLAUDE["resolve_model"],
            "validate": CLAUDE["validate_model"],
            "research": CLAUDE["research_model"],
        }
        return claude_models.get(agent)
    if key.startswith("CLAUDE_") and key.endswith("_EFFORT"):
        agent = key[len("CLAUDE_") : -len("_EFFORT")].lower()
        claude_efforts = {
            "plan": CLAUDE["plan_effort"],
            "build": CLAUDE["build_effort"],
            "resolve": CLAUDE["resolve_effort"],
            "validate": CLAUDE["validate_effort"],
            "research": CLAUDE["research_effort"],
        }
        return claude_efforts.get(agent)
    if key.startswith("LINEAR_STATE_") and key.endswith("_ID"):
        state = key[len("LINEAR_STATE_") : -len("_ID")].lower()
        states = {name: value for name, value in dict(LINEAR["states"]).items() if isinstance(value, str)}
        return states.get(state)
    return None


@dataclass
class SessionEnvironment:
    """Resolve workflow environment keys through the configuration layers.

    Every key is looked up in the project environment first, then the
    user-shared environment, and finally the ``settings.py`` defaults. A key
    that no layer provides raises :class:`EnvironmentConfigError` so a workflow
    fails and rolls back instead of running with a silent empty value.

    Attributes:
        project_environment: The project-scope env, already merged over the
            user-shared env for subprocess use.
        user_environment: The raw user-shared env, consulted before settings.
    """

    project_environment: dict[str, str]
    user_environment: dict[str, str]

    def get(self, key: str) -> str:
        """Resolve a single key through the project, user and settings layers.

        Args:
            key: The environment variable name.

        Returns:
            str: The resolved non-empty value.

        Raises:
            EnvironmentConfigError: When no layer defines the key.
        """
        if value := self.project_environment.get(key):
            return value
        if value := self.user_environment.get(key):
            return value
        if value := _settings_default(key):
            return value
        raise EnvironmentConfigError(f"Environment key {key!r} is not configured")

    @property
    def opencode_plan_model(self) -> str:
        """Return the OpenCode model used by the plan agent.

        Returns:
            str: The resolved model.
        """
        return self.get("OPENCODE_PLAN_MODEL")

    @property
    def opencode_build_model(self) -> str:
        """Return the OpenCode model used by the build and merge agents.

        Returns:
            str: The resolved model.
        """
        return self.get("OPENCODE_BUILD_MODEL")

    @property
    def opencode_resolve_model(self) -> str:
        """Return the OpenCode model used by the resolve agent.

        Returns:
            str: The resolved model.
        """
        return self.get("OPENCODE_RESOLVE_MODEL")

    @property
    def opencode_validate_model(self) -> str:
        """Return the OpenCode model used by the validate agent.

        Returns:
            str: The resolved model.
        """
        return self.get("OPENCODE_VALIDATE_MODEL")

    @property
    def opencode_research_model(self) -> str:
        """Return the OpenCode model used by the research agent.

        Returns:
            str: The resolved model.
        """
        return self.get("OPENCODE_RESEARCH_MODEL")

    @property
    def agent_harness(self) -> str:
        """Return the active agent harness, ``"opencode"`` or ``"claude"``.

        Returns:
            str: The resolved harness name.

        Raises:
            EnvironmentConfigError: When the resolved value is not a
                recognized harness.
        """
        value = self.get("AGENT_HARNESS")
        if value not in AGENT_HARNESSES:
            raise EnvironmentConfigError(f"AGENT_HARNESS must be one of {sorted(AGENT_HARNESSES)}, got {value!r}")
        return value

    @property
    def claude_plan_model(self) -> str:
        """Return the Claude model used by the plan agent.

        Returns:
            str: The resolved model.
        """
        return self.get("CLAUDE_PLAN_MODEL")

    @property
    def claude_build_model(self) -> str:
        """Return the Claude model used by the build, merge, rebase and review-fixes agents.

        Returns:
            str: The resolved model.
        """
        return self.get("CLAUDE_BUILD_MODEL")

    @property
    def claude_resolve_model(self) -> str:
        """Return the Claude model used by the resolve agent.

        Returns:
            str: The resolved model.
        """
        return self.get("CLAUDE_RESOLVE_MODEL")

    @property
    def claude_validate_model(self) -> str:
        """Return the Claude model used by the validate agent.

        Returns:
            str: The resolved model.
        """
        return self.get("CLAUDE_VALIDATE_MODEL")

    @property
    def claude_research_model(self) -> str:
        """Return the Claude model used by the research agent.

        Returns:
            str: The resolved model.
        """
        return self.get("CLAUDE_RESEARCH_MODEL")

    def claude_effort(self, agent: str) -> str | None:
        """Return the Claude effort level configured for an agent, if any.

        Unlike :meth:`get`, a missing effort is not an error: most agents run
        without an explicit effort level.

        Args:
            agent: The agent name, e.g. ``"plan"`` or ``"build"``.

        Returns:
            str | None: The resolved effort level, or None when unset.
        """
        try:
            return self.get(f"CLAUDE_{agent.upper()}_EFFORT")
        except EnvironmentConfigError:
            return None

    def claude_max_budget_usd(self, agent: str) -> float:
        """Return the Claude per-run USD budget cap configured for an agent.

        Resolution order: a per-agent override in the project or user layer,
        then a global ``CLAUDE_MAX_BUDGET_USD`` override in the project or
        user layer, then the ``settings.py`` per-agent default (which itself
        falls back to the settings-level global). Settings always provide a
        per-agent value, so the project/user global must be consulted before
        the settings layer or it would never take effect.

        Args:
            agent: The agent name, e.g. ``"plan"`` or ``"build"``.

        Returns:
            float: The resolved budget cap in USD.

        Raises:
            EnvironmentConfigError: When the resolved value is not a number.
        """
        key = f"CLAUDE_{agent.upper()}_MAX_BUDGET_USD"
        value = (
            self.project_environment.get(key)
            or self.user_environment.get(key)
            or self.project_environment.get("CLAUDE_MAX_BUDGET_USD")
            or self.user_environment.get("CLAUDE_MAX_BUDGET_USD")
        )
        if not value:
            try:
                value = self.get(key)
            except EnvironmentConfigError:
                value = self.get("CLAUDE_MAX_BUDGET_USD")
        try:
            return float(value)
        except ValueError as e:
            raise EnvironmentConfigError(f"{key} must be a number, got {value!r}") from e

    @property
    def review_models(self) -> list[ReviewModel]:
        """Return the review models configured for the active harness.

        Returns:
            list[ReviewModel]: The parsed review models; Claude entries may
                carry a ``model:effort`` pair, OpenCode entries never do.
        """
        harness = self.agent_harness
        key = "CLAUDE_REVIEW_MODELS" if harness == "claude" else "OPENCODE_REVIEW_MODELS"
        raw = self.get(key)
        entries = [entry.strip() for entry in raw.split(",") if entry.strip()]
        return [parse_review_model(entry=entry, harness=harness) for entry in entries]

    def agent_model(self, agent: str) -> str:
        """Return the model configured for an agent under the active harness.

        Args:
            agent: The agent name, e.g. ``"plan"`` or ``"build"``.

        Returns:
            str: The resolved model for the active harness.
        """
        prefix = "CLAUDE" if self.agent_harness == "claude" else "OPENCODE"
        return self.get(f"{prefix}_{agent.upper()}_MODEL")

    @property
    def openrouter_config(self) -> OpenRouterConfig:
        """Return the resolved OpenRouter configuration.

        Returns:
            OpenRouterConfig: The API key and model resolved through the env
                layers, with the base URL always taken from settings.

        Raises:
            EnvironmentConfigError: When the base URL is not configured.
        """
        base_url = _settings_default("OPENROUTER_BASE_URL")
        if not base_url:
            raise EnvironmentConfigError("Environment key 'OPENROUTER_BASE_URL' is not configured")
        return {
            "api_key": self.get("OPENROUTER_API_KEY"),
            "model": self.get("OPENROUTER_MODEL"),
            "base_url": base_url,
        }

    def linear_state(self, name: str) -> str:
        """Resolve a Linear state id from its state name.

        Args:
            name: The state name, e.g. ``"todo"`` or ``"in_review"``.

        Returns:
            str: The resolved Linear state id.
        """
        return self.get(f"LINEAR_STATE_{name.upper()}_ID")

    def linear_value(self, name: str) -> str:
        """Resolve a Linear config value from its config name.

        Args:
            name: The config name, e.g. ``"team_id"`` or ``"default_state"``.

        Returns:
            str: The resolved Linear config value.
        """
        if name == "default_state":
            return self.get("LINEAR_DEFAULT_STATE_ID")
        return self.get(f"LINEAR_{name.upper()}")


@dataclass
class Context:
    project: Project
    auto_mode: bool
    linear_task: LinearTask
    branch_name: str
    worktree_path: Path
    session: Session | None
    plan_loop: bool = False
    is_research: bool = False
    _environment: SessionEnvironment | None = None

    @property
    def environment(self) -> SessionEnvironment:
        """Return the resolved workflow environment for the context's project.

        Returns:
            SessionEnvironment: The resolver over the project env, user-shared
                env and settings defaults, built lazily and cached.
        """
        if self._environment is None:
            self._environment = SessionEnvironment(
                project_environment=self.project.environment,
                user_environment=self.project.user_environment,
            )
        return self._environment

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
class WaitlistedResponse:
    status: str = "waitlisted"
    message: str = "Your waitlist request has been recorded."
    entry_id: str | None = None


@dataclass
class WaitlistEntryUpdate:
    """Status transition with its related waitlist column changes.

    ``status`` is always applied. The other fields are applied when not None
    and keep their current column value when None. ``clear_approval``
    additionally resets every approval metadata column (``approved_by``,
    ``approved_at``, ``notified_at``, ``joined_at``) to NULL.
    """

    status: WaitlistStatus
    approved_by: str | None = None
    approved_at: datetime | None = None
    notified_at: datetime | None = None
    joined_at: datetime | None = None
    clear_approval: bool = False


@dataclass
class LoginRequest:
    email: str
    password: str


@dataclass
class UserKeysUpdateRequest:
    keys: dict
