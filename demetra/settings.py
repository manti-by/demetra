import os
from pathlib import Path


BASE_PATH = Path(__file__).resolve().parent.parent
HOME_PATH = Path.home()

DB_PATH = Path(os.environ.get("DB_PATH", HOME_PATH / ".demetra/demetra.sqlite3"))

PROJECTS_PATH = Path(os.environ.get("PROJECTS_PATH", HOME_PATH / "www"))

LINEAR_API_URL = "https://api.linear.app/graphql"
LINEAR_API_KEY = os.environ.get("LINEAR_API_KEY")
LINEAR_TEAM_ID = os.environ.get("LINEAR_TEAM_ID")

LINEAR_STATE_TODO_ID = os.environ.get("LINEAR_STATE_TODO_ID", "9f3c586f-640a-4f78-8170-90217270a0c5")
LINEAR_STATE_IN_PROGRESS_ID = os.environ.get("LINEAR_STATE_IN_PROGRESS_ID", "ded08079-9ddf-43cb-8aa8-722ba107b691")
LINEAR_STATE_IN_REVIEW_ID = os.environ.get("LINEAR_STATE_IN_REVIEW_ID", "34829892-5ab6-40a4-af4e-7a73636a78a4")
LINEAR_STATE_AWAITING_INPUT_ID = os.environ.get(
    "LINEAR_STATE_AWAITING_INPUT_ID", "e733f22b-fe21-401a-bf68-d2d374507f06"
)

OPENCODE_PATH = Path(os.environ.get("OPENCODE_PATH", HOME_PATH / ".opencode/bin/opencode"))
OPENCODE_MODEL = os.environ.get("OPENCODE_MODEL", "opencode/minimax-m2.5-free")

CURSOR_PATH = Path(os.environ.get("CURSOR_PATH", HOME_PATH / ".local/bin/cursor-agent"))

CODERABBIT_PATH = Path(os.environ.get("CODERABBIT_PATH", HOME_PATH / ".local/bin/coderabbit"))

GIT_PATH = Path(os.environ.get("GIT_PATH", "/usr/bin/git"))
GIT_WORKTREE_PATH = Path(os.environ.get("GIT_WORKTREE_PATH", HOME_PATH / ".demetra/worktrees/"))

GH_PATH = Path(os.environ.get("GH_PATH", "/usr/bin/gh"))
