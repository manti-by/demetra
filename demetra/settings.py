import os
from pathlib import Path

from demetra.library.types import (
    GitConfig,
    GitHubConfig,
    GroqConfig,
    JWTConfig,
    LinearConfig,
    OpenCodeConfig,
    PathConfig,
)


DEBUG = os.environ.get("DEBUG", "false").lower() == "true"

HOME_PATH = Path.home()

BASE_PATH = Path(__file__).resolve().parent.parent

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = int(os.environ.get("DB_PORT", 5432))
DB_USER = os.environ.get("DB_USER", "demetra")
DB_NAME = os.environ.get("DB_NAME", "demetra")
DB_PASSWORD = os.environ.get("DB_PASSWORD")

PARENT_HOME: Path | None = Path(os.environ["PARENT_HOME"]) if "PARENT_HOME" in os.environ else None

PROJECTS_PATH = Path(os.environ.get("PROJECTS_PATH", HOME_PATH / "www")).resolve()
WORKTREE_PATH = HOME_PATH / ".demetra" / "projects"

MAX_BUILD_ATTEMPTS = int(os.environ.get("MAX_BUILD_ATTEMPTS", 50))
MAX_REVIEW_ATTEMPTS = int(os.environ.get("MAX_REVIEW_ATTEMPTS", 10))
MAX_MERGE_ATTEMPTS = int(os.environ.get("MAX_MERGE_ATTEMPTS", 10))
MAX_REBASE_ATTEMPTS = int(os.environ.get("MAX_REBASE_ATTEMPTS", 10))
MAX_PLAN_ATTEMPTS = int(os.environ.get("MAX_PLAN_ATTEMPTS", 30))
MAX_RUN_ATTEMPTS = int(os.environ.get("MAX_RUN_ATTEMPTS", 3))
SUBPROCESS_TIMEOUT = int(os.environ.get("SUBPROCESS_TIMEOUT", 30 * 60))

WATCHER_POLL_INTERVAL = int(os.environ.get("WATCHER_POLL_INTERVAL", 60))
LISTENER_POLL_INTERVAL = int(os.environ.get("LISTENER_POLL_INTERVAL", 60))

LOG_PATH = Path(os.environ.get("LOG_PATH", "/var/log/demetra/demetra.log")).resolve()

LOG_DIR = LOG_PATH.parent

LOGGING: dict = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s %(levelname)-6s: %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        }
    },
    "handlers": {
        "file": {
            "level": "INFO",
            "class": "logging.FileHandler",
            "filename": LOG_PATH,
            "formatter": "standard",
        },
    },
    "loggers": {
        "": {"handlers": ["file"], "level": "INFO", "propagate": True},
    },
}

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/1")

LINEAR: LinearConfig = {
    "api_url": "https://api.linear.app/graphql",
    "client_id": os.environ.get("LINEAR_CLIENT_ID"),
    "client_secret": os.environ.get("LINEAR_CLIENT_SECRET"),
    "oauth_scope": os.environ.get("LINEAR_OAUTH_SCOPE", "read,write,comments:create"),
    "team_id": os.environ.get("LINEAR_TEAM_ID"),
    "oauth_token_url": "https://api.linear.app/oauth/token",
    "service_name": "linear",
    "feature_label_id": os.environ.get("LINEAR_FEATURE_LABEL_ID", "242cd332-e78c-42db-acc2-34441db373ab"),
    "states": {
        "prd": os.environ.get("LINEAR_STATE_PRD_ID", "c2c0b1b6-3fe0-4e60-aa04-1a1ed834f0ed"),
        "todo": os.environ.get("LINEAR_STATE_TODO_ID", "9f3c586f-640a-4f78-8170-90217270a0c5"),
        "in_progress": os.environ.get("LINEAR_STATE_IN_PROGRESS_ID", "ded08079-9ddf-43cb-8aa8-722ba107b691"),
        "in_review": os.environ.get("LINEAR_STATE_IN_REVIEW_ID", "34829892-5ab6-40a4-af4e-7a73636a78a4"),
        "awaiting_input": os.environ.get("LINEAR_STATE_AWAITING_INPUT_ID", "e733f22b-fe21-401a-bf68-d2d374507f06"),
        "done": os.environ.get("LINEAR_STATE_DONE_ID", "9f3c586f-640a-4f78-8170-90217270a0c6"),
    },
    "default_state": os.environ.get("LINEAR_DEFAULT_STATE_ID", "c2c0b1b6-3fe0-4e60-aa04-1a1ed834f0ed"),
    "filter_labels": [x for x in os.environ.get("LINEAR_FILTER_LABELS", "").split(",") if x],
}

OPENCODE: OpenCodeConfig = {
    "path": Path(os.environ.get("OPENCODE_PATH", HOME_PATH / ".opencode/bin/opencode")).resolve(),
    "plan_model": os.environ.get("OPENCODE_PLAN_MODEL", "opencode/minimax-m2.5-free"),
    "resolve_model": os.environ.get("OPENCODE_RESOLVE_MODEL", "opencode/minimax-m2.5-free"),
    "build_model": os.environ.get("OPENCODE_BUILD_MODEL", "opencode/minimax-m2.5-free"),
    "review_models": os.environ.get(
        "OPENCODE_REVIEW_MODELS",
        "opencode/big-pickle,opencode/minimax-m2.5-free",
    ).split(","),
}

CURSOR: PathConfig = {
    "path": Path(os.environ.get("CURSOR_PATH", HOME_PATH / ".local/bin/cursor-agent")).resolve(),
}

CODERABBIT: PathConfig = {
    "path": Path(os.environ.get("CODERABBIT_PATH", HOME_PATH / ".local/bin/coderabbit")).resolve(),
}

UV: PathConfig = {
    "path": Path(os.environ.get("UV_PATH", HOME_PATH / ".local/bin/uv")).resolve(),
}

GIT: GitConfig = {
    "path": Path(os.environ.get("GIT_PATH", "/usr/bin/git")).resolve(),
    "worktree_path": Path(os.environ.get("GIT_WORKTREE_PATH", HOME_PATH / ".demetra/worktrees/")).resolve(),
}

GITHUB: GitHubConfig = {
    "path": Path(os.environ.get("GH_PATH", "/usr/bin/gh")).resolve(),
    "oauth": {
        "client_id": os.environ.get("GITHUB_CLIENT_ID"),
        "client_secret": os.environ.get("GITHUB_CLIENT_SECRET"),
        "redirect_uri": os.environ.get("GITHUB_REDIRECT_URI", "https://demetra.manti.by/github/callback"),
        "oauth_url": "https://github.com/login/oauth/authorize",
        "token_url": "https://github.com/login/oauth/access_token",
        "user_url": "https://api.github.com/user",
    },
    "webhook": {
        "secret": os.environ.get("GITHUB_WEBHOOK_SECRET"),
    },
    "token": os.environ.get("GITHUB_TOKEN"),
}

JWT: JWTConfig = {
    "secret_key": os.environ.get("JWT_SECRET_KEY"),
    "algorithm": "HS256",
    "expiration_days": 14,
}

GROQ: GroqConfig = {
    "api_key": os.environ.get("GROQ_API_KEY"),
    "model": os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant"),
}

SECRET_KEY = os.environ.get("SECRET_KEY")

ENCRYPTION_SALT = os.environ.get("ENCRYPTION_SALT")

DEFAULT_USER_ID = os.environ.get("DEFAULT_USER_ID")
