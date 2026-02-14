import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

PROJECTS_PATH = Path(os.environ.get("PROJECTS_PATH", "/home/manti/www"))

LINEAR_API_URL = "https://api.linear.app/graphql"
LINEAR_API_KEY = os.environ.get("LINEAR_API_KEY")
LINEAR_TEAM_ID = os.environ.get("LINEAR_TEAM_ID")

OPENCODE_PATH = Path(os.environ.get("OPENCODE_PATH", "/home/manti/.opencode/bin/opencode"))

CODERABBIT_PATH = Path(os.environ.get("CODERABBIT_PATH", "/home/manti/.local/bin/coderabbit"))
