import os
from pathlib import Path

from demetra.types import (
    CodeRabbitConfig,
    CursorConfig,
    GitConfig,
    GitHubConfig,
    GroqConfig,
    LinearConfig,
    OpenCodeConfig,
)


HOME_PATH = Path.home()

BASE_PATH = Path(__file__).resolve().parent.parent

DB_PATH = Path(os.environ.get("DB_PATH", HOME_PATH / ".demetra/demetra.sqlite3"))

PROJECTS_PATH = Path(os.environ.get("PROJECTS_PATH", HOME_PATH / "www"))

MAX_BUILD_ATTEMPTS = int(os.environ.get("MAX_BUILD_ATTEMPTS", 5))

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
    "projects": {
        "odin": os.environ.get("LINEAR_ODIN_PROJECT_ID", "57af4fbe-2ee1-4faf-8968-e9b50063afff"),
        "demetra": os.environ.get("LINEAR_DEMETRA_PROJECT_ID", "59773b61-cdd2-4f93-95ec-d6a5a1b5b33c"),
        "coruscant": os.environ.get("LINEAR_CORUSCANT_PROJECT_ID", "8ee7cd23-8fc9-4304-8ba3-997c76d06714"),
    },
    "default_state": os.environ.get("LINEAR_DEFAULT_STATE_ID", "c2c0b1b6-3fe0-4e60-aa04-1a1ed834f0ed"),
    "default_project": os.environ.get("LINEAR_DEFAULT_PROJECT_ID", "59773b61-cdd2-4f93-95ec-d6a5a1b5b33c"),
}

OPENCODE: OpenCodeConfig = {
    "path": Path(os.environ.get("OPENCODE_PATH", HOME_PATH / ".opencode/bin/opencode")),
    "model": os.environ.get("OPENCODE_MODEL", "opencode/minimax-m2.5-free"),
}

CURSOR: CursorConfig = {
    "path": Path(os.environ.get("CURSOR_PATH", HOME_PATH / ".local/bin/cursor-agent")),
}

CODERABBIT: CodeRabbitConfig = {
    "path": Path(os.environ.get("CODERABBIT_PATH", HOME_PATH / ".local/bin/coderabbit")),
}

GIT: GitConfig = {
    "path": Path(os.environ.get("GIT_PATH", "/usr/bin/git")),
    "worktree_path": Path(os.environ.get("GIT_WORKTREE_PATH", HOME_PATH / ".demetra/worktrees/")),
}

GITHUB: GitHubConfig = {
    "path": Path(os.environ.get("GH_PATH", "/usr/bin/gh")),
}

GROQ: GroqConfig = {
    "api_key": os.environ.get("GROQ_API_KEY"),
    "model": os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant"),
}
