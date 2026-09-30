from pathlib import Path
from typing import Literal, TypedDict


CockieSamesite = Literal["lax", "strict", "none"]

WaitlistEntryType = Literal["email", "github_username"]

WaitlistStatus = Literal["pending", "approved", "rejected", "joined"]


class DBConfig(TypedDict):
    host: str
    port: int
    user: str
    name: str
    password: str | None


class LinearStates(TypedDict):
    prd: str
    todo: str
    in_progress: str
    in_review: str
    awaiting_input: str
    done: str


class LinearConfig(TypedDict):
    api_url: str
    client_id: str | None
    client_secret: str | None
    oauth_scope: str
    team_id: str | None
    oauth_token_url: str
    service_name: str
    feature_label_id: str
    backend_label_id: str
    frontend_label_id: str
    states: LinearStates
    default_state: str
    filter_labels: list[str]
    research_labels: list[str]


class ClickUpStates(TypedDict):
    prd: str
    todo: str
    in_progress: str
    in_review: str
    awaiting_input: str
    done: str


class ClickUpConfig(TypedDict):
    api_url: str
    api_token: str | None
    team_id: str | None
    list_id: str | None
    service_name: str
    feature_tag: str
    backend_tag: str
    frontend_tag: str
    states: ClickUpStates
    default_state: str
    filter_labels: list[str]
    research_labels: list[str]


class PathConfig(TypedDict):
    path: Path


class OpenCodeConfig(PathConfig):
    plan_model: str
    resolve_model: str
    build_model: str
    review_models: list[str]
    validate_model: str
    research_model: str


class ClaudeConfig(PathConfig):
    plan_model: str
    plan_effort: str | None
    resolve_model: str
    resolve_effort: str | None
    research_model: str
    research_effort: str | None
    build_model: str
    build_effort: str | None
    validate_model: str
    validate_effort: str | None
    review_models: list[str]


class GitConfig(PathConfig):
    worktree_path: Path


class GitHubOAuthConfig(TypedDict):
    client_id: str | None
    client_secret: str | None
    redirect_uri: str
    oauth_url: str
    token_url: str
    user_url: str


class GitHubWebhookConfig(TypedDict):
    secret: str | None


class GitHubConfig(PathConfig):
    oauth: GitHubOAuthConfig
    webhook: GitHubWebhookConfig
    token: str | None


class JWTConfig(TypedDict):
    secret_key: str | None
    algorithm: str
    expiration_days: int


class OpenRouterConfig(TypedDict):
    api_key: str | None
    model: str
    base_url: str


class LangSmithConfig(TypedDict):
    tracing: bool
    endpoint: str
    api_key: str | None
    project: str
