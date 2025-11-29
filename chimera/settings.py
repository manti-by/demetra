import os
from pathlib import Path

PROJECTS_PATH = os.getenv("PROJECTS_PATH", "/projects")
LINEAR_API_KEY = os.getenv("LINEAR_API_KEY", "")
LINEAR_API_URL = os.getenv("LINEAR_API_URL", "https://api.linear.app/graphql")
LINEAR_TEAM_ID = os.getenv("LINEAR_TEAM_ID", "")

def get_linear_client():
    if not LINEAR_API_KEY:
        raise ValueError("LINEAR_API_KEY not set")
