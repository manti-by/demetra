import os
from pathlib import Path


BASE_PATH = Path(__file__).resolve().parent.parent
HOME_PATH = Path.home()

PROJECTS_PATH = Path(os.environ.get("PROJECTS_PATH", HOME_PATH / "www"))

LINEAR_API_URL = "https://api.linear.app/graphql"
LINEAR_API_KEY = os.environ.get("LINEAR_API_KEY")
LINEAR_TEAM_ID = os.environ.get("LINEAR_TEAM_ID")

OPENCODE_PATH = Path(os.environ.get("OPENCODE_PATH", HOME_PATH / ".opencode/bin/opencode"))

CODERABBIT_PATH = Path(os.environ.get("CODERABBIT_PATH", HOME_PATH / ".local/bin/coderabbit"))

GIT_PATH = Path(os.environ.get("GIT_PATH", "/usr/bin/git"))

GIT_WORKTREE_PATH = Path(os.environ.get("GIT_WORKTREE_PATH", HOME_PATH / ".local/demetra/worktrees/"))
