from pathlib import Path
from typing import TypedDict


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
    states: LinearStates
    default_state: str
    filter_labels: list[str]


class PathConfig(TypedDict):
    path: Path


class OpenCodeConfig(PathConfig):
    plan_model: str
    resolve_model: str
    build_model: str
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


class GroqConfig(TypedDict):
    api_key: str | None
    model: str
