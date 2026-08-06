import os
from pathlib import Path

from demetra.library.exceptions import SettingsError
from demetra.library.types import (
    GitConfig,
    GitHubConfig,
    GroqConfig,
    JWTConfig,
    LinearConfig,
    OpenCodeConfig,
    PathConfig,
)
from demetra.services.utils import env_get_bool, env_get_int, env_get_list, get_cookie_samesite


DEBUG = env_get_bool("DEBUG", False)

HOME_PATH = Path.home()

BASE_PATH = Path(__file__).resolve().parent.parent

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = env_get_int("DB_PORT", 5432)
DB_USER = os.environ.get("DB_USER", "demetra")
DB_NAME = os.environ.get("DB_NAME", "demetra")
DB_PASSWORD = os.environ.get("DB_PASSWORD")

PARENT_HOME: Path | None = Path(os.environ["PARENT_HOME"]) if "PARENT_HOME" in os.environ else None

PROJECTS_PATH = Path(os.environ.get("PROJECTS_PATH", HOME_PATH / "www")).resolve()
WORKTREE_PATH = HOME_PATH / ".demetra" / "projects"

MAX_BUILD_ATTEMPTS = env_get_int("MAX_BUILD_ATTEMPTS", 50)
MAX_REVIEW_ATTEMPTS = env_get_int("MAX_REVIEW_ATTEMPTS", 10)
MAX_MERGE_ATTEMPTS = env_get_int("MAX_MERGE_ATTEMPTS", 10)
MAX_REBASE_ATTEMPTS = env_get_int("MAX_REBASE_ATTEMPTS", 10)
MAX_PLAN_ATTEMPTS = env_get_int("MAX_PLAN_ATTEMPTS", 30)
MAX_RUN_ATTEMPTS = env_get_int("MAX_RUN_ATTEMPTS", 5)
MAX_LISTENER_ATTEMPTS = env_get_int("MAX_LISTENER_ATTEMPTS", 5)
SUBPROCESS_TIMEOUT = env_get_int("SUBPROCESS_TIMEOUT", 30 * 60)
CONTEXT_COMPACTION_THRESHOLD = env_get_int("CONTEXT_COMPACTION_THRESHOLD", 100_000)

FEATURES: dict = {
    "is_ruff_enabled": env_get_bool("IS_RUFF_ENABLED", False),
    "is_pytest_enabled": env_get_bool("IS_PYTEST_ENABLED", False),
}


WIKI_GROQ_BUDGET_FILES = env_get_int("WIKI_GROQ_BUDGET_FILES", 8)
WIKI_GROQ_BUDGET_LINES = env_get_int("WIKI_GROQ_BUDGET_LINES", 200)
WIKI_DIFF_HUNK_CAP = env_get_int("WIKI_DIFF_HUNK_CAP", 200)
WIKI_BUILD_PLAN_CAP = env_get_int("WIKI_BUILD_PLAN_CAP", 800)
WIKI_REVALIDATION_ENABLED = env_get_bool("WIKI_REVALIDATION_ENABLED", False)

WATCHER_POLL_INTERVAL = env_get_int("WATCHER_POLL_INTERVAL", 60)
LISTENER_POLL_INTERVAL = env_get_int("LISTENER_POLL_INTERVAL", 60)

LOG_PATH = Path(os.environ.get("LOG_PATH", "/var/log/demetra/demetra.log")).resolve()

LOG_DIR = LOG_PATH.parent

LOGGING: dict = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "ansi_strip": {
            "()": "demetra.services.utils.AnsiStrippingFilter",
        },
    },
    "formatters": {
        "standard": {
            "format": "%(asctime)s %(levelname)-6s: %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        }
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "standard",
            "filters": ["ansi_strip"],
        },
        "file": {
            "level": "INFO",
            "class": "logging.FileHandler",
            "filename": LOG_PATH,
            "formatter": "standard",
            "filters": ["ansi_strip"],
        },
    },
    "loggers": {
        "": {"handlers": ["console", "file"], "level": os.environ.get("LOG_LEVEL", "DEBUG"), "propagate": True},
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
    "filter_labels": env_get_list("LINEAR_FILTER_LABELS", []),
}

OPENCODE: OpenCodeConfig = {
    "path": Path(os.environ.get("OPENCODE_PATH", HOME_PATH / ".opencode/bin/opencode")).resolve(),
    "plan_model": os.environ.get("OPENCODE_PLAN_MODEL", "opencode-go/minimax-m3"),
    "resolve_model": os.environ.get("OPENCODE_RESOLVE_MODEL", "opencode-go/qwen3.7-max"),
    "build_model": os.environ.get("OPENCODE_BUILD_MODEL", "opencode-go/deepseek-v4-flash"),
    "review_models": env_get_list(
        "OPENCODE_REVIEW_MODELS", ["opencode-go/qwen3.7-plus", "opencode-go/glm-5.2", "opencode-go/kimi-k2.7-code"]
    ),
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

COOKIE_SECURE = env_get_bool("COOKIE_SECURE", True)

CORS_ALLOWED_ORIGINS = env_get_list("CORS_ALLOWED_ORIGINS", ["http://localhost:5173", "http://localhost:8000"])

if "*" in CORS_ALLOWED_ORIGINS:
    raise SettingsError("CORS_ALLOWED_ORIGINS must contain explicit origins when credentials are enabled")

COOKIE_SAMESITE = get_cookie_samesite(is_cockie_secure=COOKIE_SECURE)
