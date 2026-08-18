from pathlib import Path

from demetra.library.exceptions import SettingsError
from demetra.library.types import (
    GitConfig,
    GitHubConfig,
    GroqConfig,
    JWTConfig,
    LinearConfig,
    OpenCodeConfig,
    OpenRouterConfig,
    PathConfig,
)
from demetra.services.runtime.utils import (
    env_get_bool,
    env_get_int,
    env_get_list,
    env_get_path,
    env_get_str,
    get_cookie_samesite,
    parse_os_env_project_optins,
    validate_llm_base_url,
)


DEBUG = env_get_bool("DEBUG", False)

HOME_PATH = Path.home()

BASE_PATH = Path(__file__).resolve().parent.parent

DB_HOST = env_get_str("DB_HOST", "localhost")
DB_PORT = env_get_int("DB_PORT", 5432)
DB_USER = env_get_str("DB_USER", "demetra")
DB_NAME = env_get_str("DB_NAME", "demetra")
DB_PASSWORD = env_get_str("DB_PASSWORD", None)

PARENT_HOME: Path | None = env_get_path("PARENT_HOME", None)

PROJECTS_PATH = env_get_path("PROJECTS_PATH", HOME_PATH / "www")
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

WIKI: dict = {
    "llm_budget_files": env_get_int("WIKI_LLM_BUDGET_FILES", env_get_int("WIKI_GROQ_BUDGET_FILES", 8)),
    "llm_budget_lines": env_get_int("WIKI_LLM_BUDGET_LINES", env_get_int("WIKI_GROQ_BUDGET_LINES", 200)),
    "diff_hunk_cap": env_get_int("WIKI_DIFF_HUNK_CAP", 200),
    "build_plan_cap": env_get_int("WIKI_BUILD_PLAN_CAP", 800),
    "revalidation_enabled": env_get_bool("WIKI_REVALIDATION_ENABLED", False),
}

WATCHER_POLL_INTERVAL = env_get_int("WATCHER_POLL_INTERVAL", 60)
LISTENER_POLL_INTERVAL = env_get_int("LISTENER_POLL_INTERVAL", 60)

ALLOWLIST_ENABLED = env_get_bool("IS_ALLOWLIST_ENABLED", False)
ALLOWLIST_SEED_FILE = env_get_str("ALLOWLIST_SEED_FILE", None)

OS_ENV_PROJECT_OPTINS = parse_os_env_project_optins(env_get_str("OS_ENV_PROJECT_OPTINS", None))

LOG_PATH = env_get_path("LOG_PATH", Path("/var/log/demetra/demetra.log"))

LOG_DIR = LOG_PATH.parent

LOGGING: dict = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "ansi_strip": {
            "()": "demetra.services.runtime.utils.AnsiStrippingFilter",
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
        "": {"handlers": ["console", "file"], "level": env_get_str("LOG_LEVEL", "DEBUG"), "propagate": True},
    },
}

REDIS_URL = env_get_str("REDIS_URL", "redis://localhost:6379/1")

LINEAR: LinearConfig = {
    "api_url": "https://api.linear.app/graphql",
    "client_id": env_get_str("LINEAR_CLIENT_ID", None),
    "client_secret": env_get_str("LINEAR_CLIENT_SECRET", None),
    "oauth_scope": env_get_str("LINEAR_OAUTH_SCOPE", "read,write,comments:create"),
    "team_id": env_get_str("LINEAR_TEAM_ID", None),
    "oauth_token_url": "https://api.linear.app/oauth/token",
    "service_name": "linear",
    "feature_label_id": env_get_str("LINEAR_FEATURE_LABEL_ID", "242cd332-e78c-42db-acc2-34441db373ab"),
    "states": {
        "prd": env_get_str("LINEAR_STATE_PRD_ID", "c2c0b1b6-3fe0-4e60-aa04-1a1ed834f0ed"),
        "todo": env_get_str("LINEAR_STATE_TODO_ID", "9f3c586f-640a-4f78-8170-90217270a0c5"),
        "in_progress": env_get_str("LINEAR_STATE_IN_PROGRESS_ID", "ded08079-9ddf-43cb-8aa8-722ba107b691"),
        "in_review": env_get_str("LINEAR_STATE_IN_REVIEW_ID", "34829892-5ab6-40a4-af4e-7a73636a78a4"),
        "awaiting_input": env_get_str("LINEAR_STATE_AWAITING_INPUT_ID", "e733f22b-fe21-401a-bf68-d2d374507f06"),
        "done": env_get_str("LINEAR_STATE_DONE_ID", "9f3c586f-640a-4f78-8170-90217270a0c6"),
    },
    "default_state": env_get_str("LINEAR_DEFAULT_STATE_ID", "c2c0b1b6-3fe0-4e60-aa04-1a1ed834f0ed"),
    "filter_labels": env_get_list("LINEAR_FILTER_LABELS", []),
}

OPENCODE: OpenCodeConfig = {
    "path": env_get_path("OPENCODE_PATH", HOME_PATH / ".opencode/bin/opencode"),
    "plan_model": env_get_str("OPENCODE_PLAN_MODEL", "opencode-go/minimax-m3"),
    "resolve_model": env_get_str("OPENCODE_RESOLVE_MODEL", "opencode-go/qwen3.7-max"),
    "build_model": env_get_str("OPENCODE_BUILD_MODEL", "opencode-go/deepseek-v4-flash"),
    "validate_model": env_get_str("OPENCODE_VALIDATE_MODEL", "opencode-go/deepseek-v4-flash"),
    "review_models": env_get_list(
        "OPENCODE_REVIEW_MODELS", ["opencode-go/qwen3.7-plus", "opencode-go/glm-5.2", "opencode-go/kimi-k2.7-code"]
    ),
}

CURSOR: PathConfig = {
    "path": env_get_path("CURSOR_PATH", HOME_PATH / ".local/bin/cursor-agent"),
}

CODERABBIT: PathConfig = {
    "path": env_get_path("CODERABBIT_PATH", HOME_PATH / ".local/bin/coderabbit"),
}

UV: PathConfig = {
    "path": env_get_path("UV_PATH", HOME_PATH / ".local/bin/uv"),
}

GIT: GitConfig = {
    "path": env_get_path("GIT_PATH", Path("/usr/bin/git")),
    "worktree_path": env_get_path("GIT_WORKTREE_PATH", HOME_PATH / ".demetra/worktrees/"),
}

GITHUB: GitHubConfig = {
    "path": env_get_path("GH_PATH", Path("/usr/bin/gh")),
    "oauth": {
        "client_id": env_get_str("GITHUB_CLIENT_ID", None),
        "client_secret": env_get_str("GITHUB_CLIENT_SECRET", None),
        "redirect_uri": env_get_str("GITHUB_REDIRECT_URI", "https://demetra.manti.by/github/callback"),
        "oauth_url": "https://github.com/login/oauth/authorize",
        "token_url": "https://github.com/login/oauth/access_token",
        "user_url": "https://api.github.com/user",
    },
    "webhook": {
        "secret": env_get_str("GITHUB_WEBHOOK_SECRET", None),
    },
    "token": env_get_str("GITHUB_TOKEN", None),
}

JWT: JWTConfig = {
    "secret_key": env_get_str("JWT_SECRET_KEY", None),
    "algorithm": "HS256",
    "expiration_days": 14,
}

GROQ: GroqConfig = {
    "api_key": env_get_str("GROQ_API_KEY", None),
    "model": env_get_str("GROQ_MODEL", "openai/gpt-oss-120b"),
}

OPENROUTER: OpenRouterConfig = {
    "api_key": env_get_str("OPENROUTER_API_KEY", None),
    "model": env_get_str("OPENROUTER_MODEL", "openai/gpt-oss-120b"),
    "base_url": validate_llm_base_url(env_get_str("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")),
}

SECRET_KEY = env_get_str("SECRET_KEY", None)

ENCRYPTION_SALT = env_get_str("ENCRYPTION_SALT", None)

DEFAULT_USER_ID = env_get_str("DEFAULT_USER_ID", None)

COOKIE_SECURE = env_get_bool("COOKIE_SECURE", True)

CORS_ALLOWED_ORIGINS = env_get_list("CORS_ALLOWED_ORIGINS", ["http://localhost:5173", "http://localhost:8000"])

if "*" in CORS_ALLOWED_ORIGINS:
    raise SettingsError("CORS_ALLOWED_ORIGINS must contain explicit origins when credentials are enabled")

COOKIE_SAMESITE = get_cookie_samesite(is_cockie_secure=COOKIE_SECURE)
