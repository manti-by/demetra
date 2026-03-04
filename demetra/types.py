from pathlib import Path
from typing import TypedDict


class LinearStates(TypedDict):
    prd: str
    todo: str
    in_progress: str
    in_review: str
    awaiting_input: str
    done: str


class LinearProjects(TypedDict):
    odin: str
    demetra: str
    coruscant: str


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
    projects: LinearProjects
    default_state: str
    default_project: str


class OpenCodeConfig(TypedDict):
    path: Path
    model: str


class CursorConfig(TypedDict):
    path: Path


class CodeRabbitConfig(TypedDict):
    path: Path


class GitConfig(TypedDict):
    path: Path
    worktree_path: Path


class GitHubConfig(TypedDict):
    path: Path


class GroqConfig(TypedDict):
    api_key: str | None
    model: str
