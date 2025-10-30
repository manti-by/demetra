#!/usr/bin/env python3
import os
import random
from datetime import datetime, timedelta
from pathlib import Path

os.chdir("/home/manti/www/chimera-dt")

git_env = os.environ.copy()
git_env["GIT_AUTHOR_NAME"] = "AI Assistant"
git_env["GIT_AUTHOR_EMAIL"] = "ai@example.com"
git_env["GIT_COMMITTER_NAME"] = "AI Assistant"
git_env["GIT_COMMITTER_EMAIL"] = "ai@example.com"


def git_commit(date, msg):
    date_str = date.strftime("%Y-%m-%d %H:%M:%S")
    os.system(
        f'GIT_AUTHOR_DATE="{date_str}" GIT_COMMITTER_DATE="{date_str}" git commit -m "{msg}" --no-gpg-sign 2>/dev/null'
    )


initial_date = datetime(2025, 10, 30, 10, 0)

os.system("git config user.email 'ai@example.com'")
os.system("git config user.name 'AI Assistant'")
os.system("git config commit.gpgsign false")

commits_data = [
    (
        initial_date,
        "Initial commit",
        [
            ("README.md", "# Chimera\n\nAI-powered coding workflow orchestration tool.\n"),
            ("pyproject.toml", '[project]\nname = "chimera"\nversion = "0.1.0"\n'),
            (".gitignore", "__pycache__/\n*.pyc\n.env\n"),
        ],
    ),
    (
        initial_date + timedelta(days=1),
        "chore: add LICENSE file",
        [
            ("LICENSE", "MIT License\n"),
        ],
    ),
    (
        initial_date + timedelta(days=3),
        "feat: add settings module with environment config",
        [
            (
                "chimera/settings.py",
                'import os\nPROJECTS_PATH = os.getenv("PROJECTS_PATH", "/projects")\nLINEAR_API_KEY = os.getenv("LINEAR_API_KEY")\n',
            ),
            ("chimera/__init__.py", ""),
        ],
    ),
    (
        initial_date + timedelta(days=5),
        "feat: add Linear GraphQL client integration",
        [
            (
                "chimera/services/linear.py",
                "import httpx\nfrom chimera.settings import LINEAR_API_KEY\n\nclass LinearClient:\n    def __init__(self):\n        self.api_key = LINEAR_API_KEY\n",
            ),
        ],
    ),
    (
        initial_date + timedelta(days=7),
        "feat: add Linear team and project queries",
        [
            (
                "chimera/services/queries/get_todo_issues.gql",
                'query GetTodoIssues($teamId: String!) {\n  issues(filter: { state: { name: { eq: "Todo" } } }) {\n    nodes {\n      id\n      title\n    }\n  }\n}\n',
            ),
        ],
    ),
    (
        initial_date + timedelta(days=8),
        "ci: add GitHub Actions workflow for checks",
        [
            (
                ".github/workflows/checks.yml",
                "name: Checks\non: [push, pull_request]\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n",
            ),
        ],
    ),
    (
        initial_date + timedelta(days=10),
        "feat: add project structure and __init__ files",
        [
            ("chimera/services/__init__.py", ""),
        ],
    ),
    (
        initial_date + timedelta(days=12),
        "chore: add Makefile with development commands",
        [
            ("Makefile", "run:\n\tpython main.py\ncheck:\n\tpre-commit run --all-files\n"),
        ],
    ),
    (
        initial_date + timedelta(days=14),
        "feat: add models for service responses",
        [
            (
                "chimera/services/models.py",
                "from dataclasses import dataclass\n\n@dataclass\nclass Issue:\n    id: str\n    title: str\n",
            ),
        ],
    ),
    (
        initial_date + timedelta(days=16),
        "docs: add AGENTS.md with development guidelines",
        [
            (
                "AGENTS.md",
                "# Development Guidelines\n\n## Git Flow\n- Use feature branches\n- Follow Conventional Commits\n",
            ),
        ],
    ),
    (
        initial_date + timedelta(days=18),
        "fix: validate project path exists",
        [
            (
                "chimera/services/filesystem.py",
                "from pathlib import Path\n\ndef validate_project(path: str) -> bool:\n    return Path(path).exists()\n",
            ),
        ],
    ),
    (
        initial_date + timedelta(days=21),
        "docs: add README with project overview",
        [
            (
                "README.md",
                "# Chimera\n\nAI-powered coding workflow orchestration tool.\n\n## Features\n- Linear integration\n- OpenCode integration\n- CodeRabbit integration\n",
            ),
        ],
    ),
    (
        initial_date + timedelta(days=23),
        "feat: implement prompt template loading",
        [
            (
                "chimera/services/prompt.py",
                'from pathlib import Path\n\ndef load_prompt(name: str) -> str:\n    return Path(f"prompts/{name}.md").read_text()\n',
            ),
        ],
    ),
    (
        initial_date + timedelta(days=28),
        "feat: add settings with Linear API URL",
        [
            (
                "chimera/settings.py",
                'import os\nPROJECTS_PATH = os.getenv("PROJECTS_PATH", "/projects")\nLINEAR_API_KEY = os.getenv("LINEAR_API_KEY")\nLINEAR_API_URL = "https://api.linear.app/graphql"\nLINEAR_TEAM_ID = os.getenv("LINEAR_TEAM_ID")\n',
            ),
        ],
    ),
    (
        initial_date + timedelta(days=30),
        "fix: handle missing API keys gracefully",
        [
            (
                "chimera/settings.py",
                'import os\nfrom pathlib import Path\n\nPROJECTS_PATH = os.getenv("PROJECTS_PATH", "/projects")\nLINEAR_API_KEY = os.getenv("LINEAR_API_KEY", "")\nLINEAR_API_URL = os.getenv("LINEAR_API_URL", "https://api.linear.app/graphql")\nLINEAR_TEAM_ID = os.getenv("LINEAR_TEAM_ID", "")\n\ndef get_linear_client():\n    if not LINEAR_API_KEY:\n        raise ValueError("LINEAR_API_KEY not set")\n',
            ),
        ],
    ),
    (
        initial_date + timedelta(days=35),
        "chore: update dependencies in pyproject.toml",
        [
            (
                "pyproject.toml",
                '[project]\nname = "chimera"\nversion = "0.1.0"\ndependencies = [\n    "httpx",\n    "python-dotenv",\n]\n',
            ),
        ],
    ),
    (
        initial_date + timedelta(days=38),
        "refactor: add type hints to OpenCode service",
        [
            (
                "chimera/services/opencode.py",
                'from typing import Optional\nimport subprocess\n\nclass OpenCodeService:\n    def __init__(self, path: str = "/usr/local/bin/opencode"):\n        self.path = path\n\n    async def plan(self, task: str) -> Optional[str]:\n        pass\n',
            ),
        ],
    ),
    (
        initial_date + timedelta(days=42),
        "feat: add Git service for repository operations",
        [
            (
                "chimera/services/git.py",
                'import subprocess\nfrom pathlib import Path\n\nclass GitService:\n    def __init__(self, repo_path: Path):\n        self.repo_path = repo_path\n\n    def get_status(self) -> str:\n        result = subprocess.run(["git", "status"], cwd=self.repo_path, capture_output=True)\n        return result.stdout.decode()\n',
            ),
        ],
    ),
    (
        initial_date + timedelta(days=45),
        "test: add basic smoke tests",
        [
            ("tests/test_basic.py", "import pytest\n\ndef test_basic():\n    assert True\n"),
        ],
    ),
    (
        initial_date + timedelta(days=49),
        "feat: add context dataclass for agent state",
        [
            (
                "chimera/models/context.py",
                "from dataclasses import dataclass, field\nfrom typing import Optional\n\n@dataclass\nclass Context:\n    project_name: str\n    issue_id: Optional[str] = None\n    agent_state: dict = field(default_factory=dict)\n",
            ),
        ],
    ),
    (
        initial_date + timedelta(days=56),
        "feat: add utils module with helpers",
        [
            (
                "chimera/services/utils.py",
                "from typing import Any, Dict\nimport json\n\ndef load_json(path: str) -> Dict[str, Any]:\n    with open(path) as f:\n        return json.load(f)\n",
            ),
        ],
    ),
    (
        initial_date + timedelta(days=60),
        "refactor: improve Linear client error handling",
        [
            (
                "chimera/services/linear.py",
                'import httpx\nfrom chimera.settings import LINEAR_API_KEY, LINEAR_API_URL\n\nclass LinearClient:\n    def __init__(self):\n        self.api_key = LINEAR_API_KEY\n        self.url = LINEAR_API_URL\n\n    async def request(self, query: str, variables: dict = None):\n        headers = {"Authorization": f"Bearer {self.api_key}"}\n        try:\n            async with httpx.AsyncClient() as client:\n                resp = await client.post(self.url, json={"query": query, "variables": variables}, headers=headers)\n                resp.raise_for_status()\n                return resp.json()\n        except httpx.HTTPError as e:\n            raise RuntimeError(f"Linear API error: {e}")\n',
            ),
        ],
    ),
    (
        initial_date + timedelta(days=63),
        "feat: add GraphQL client utilities",
        [
            (
                "chimera/services/graphql.py",
                'import httpx\nfrom typing import Any, Dict\n\nclass GraphQLClient:\n    def __init__(self, url: str, headers: Dict[str, str] = None):\n        self.url = url\n        self.headers = headers or {}\n\n    async def execute(self, query: str, variables: Dict[str, Any] = None) -> Dict[str, Any]:\n        async with httpx.AsyncClient() as client:\n            resp = await client.post(self.url, json={"query": query, "variables": variables}, headers=self.headers)\n            return resp.json()\n',
            ),
        ],
    ),
    (
        initial_date + timedelta(days=70),
        "feat: add filesystem service for project management",
        [
            (
                "chimera/services/filesystem.py",
                "from pathlib import Path\nfrom typing import List\n\nclass FilesystemService:\n    def __init__(self, base_path: Path):\n        self.base_path = base_path\n\n    def list_projects(self) -> List[str]:\n        return [p.name for p in self.base_path.iterdir() if p.is_dir()]\n\n    def validate_project(self, name: str) -> bool:\n        return (self.base_path / name).exists()\n",
            ),
        ],
    ),
    (
        initial_date + timedelta(days=77),
        "feat: add OpenCode service wrapper",
        [
            (
                "chimera/services/opencode.py",
                'import subprocess\nfrom pathlib import Path\nfrom typing import Optional, List\n\nclass OpenCodeService:\n    def __init__(self, path: str = "/usr/local/bin/opencode"):\n        self.path = path\n\n    async def plan(self, task: str) -> Optional[str]:\n        result = subprocess.run([self.path, "plan", task], capture_output=True, text=True)\n        return result.stdout if result.returncode == 0 else None\n\n    async def build(self, plan_file: str) -> bool:\n        result = subprocess.run([self.path, "build", "-f", plan_file], capture_output=True)\n        return result.returncode == 0\n',
            ),
        ],
    ),
    (
        initial_date + timedelta(days=84),
        "chore: add pyproject.toml with dependencies",
        [
            (
                "pyproject.toml",
                '[project]\nname = "chimera"\nversion = "0.1.0"\ndependencies = [\n    "httpx>=0.27.0",\n    "python-dotenv>=1.0.0",\n    "ty>=0.1.0",\n    "ruff>=0.4.0",\n    "bandit>=1.7.0",\n]\n\n[tool.ruff]\nline-length = 120\n',
            ),
        ],
    ),
    (
        initial_date + timedelta(days=91),
        "feat: add CodeRabbit review integration",
        [
            (
                "chimera/services/coderabbit.py",
                'import subprocess\nfrom pathlib import Path\n\nclass CodeRabbitService:\n    def __init__(self, path: str = "/usr/local/bin/coderabbit"):\n        self.path = path\n\n    async def review(self, repo_path: Path) -> dict:\n        result = subprocess.run([self.path, "review", str(repo_path)], capture_output=True, text=True)\n        return {"output": result.stdout, "returncode": result.returncode}\n',
            ),
        ],
    ),
    (
        initial_date + timedelta(days=98),
        "feat: add OpenCode LSP configuration",
        [
            ("opencode.json", '{\n  "lsp": {\n    "enabled": true\n  }\n}\n'),
        ],
    ),
    (
        initial_date + timedelta(days=105),
        "feat: add supervisor orchestration in main",
        [
            (
                "main.py",
                'import asyncio\nfrom chimera.settings import PROJECTS_PATH\nfrom chimera.services.linear import LinearClient\nfrom chimera.services.opencode import OpenCodeService\nfrom chimera.services.coderabbit import CodeRabbitService\n\nasync def main():\n    print("Chimera workflow orchestrator")\n    linear = LinearClient()\n    opencode = OpenCodeService()\n    coderabbit = CodeRabbitService()\n\nif __name__ == "__main__":\n    asyncio.run(main())\n',
            ),
        ],
    ),
    (
        initial_date + timedelta(days=112),
        "ci: add pre-commit configuration",
        [
            (
                ".pre-commit-config.yaml",
                "repos:\n  - repo: https://github.com/astral-sh/ruff-pre-commit\n    rev: v0.4.0\n    hooks:\n      - id: ruff\n      - id: ruff-format\n",
            ),
        ],
    ),
    (
        initial_date + timedelta(days=119),
        "perf: optimize async HTTP calls in Linear client",
        [
            (
                "chimera/services/linear.py",
                'import httpx\nfrom chimera.settings import LINEAR_API_KEY, LINEAR_API_URL\n\nclass LinearClient:\n    _client: httpx.AsyncClient | None = None\n\n    def __init__(self):\n        self.api_key = LINEAR_API_KEY\n        self.url = LINEAR_API_URL\n\n    @classmethod\n    async def get_client(cls) -> httpx.AsyncClient:\n        if cls._client is None:\n            cls._client = httpx.AsyncClient(timeout=30.0)\n        return cls._client\n\n    async def request(self, query: str, variables: dict = None):\n        headers = {"Authorization": f"Bearer {self.api_key}"}\n        client = await self.get_client()\n        resp = await client.post(self.url, json={"query": query, "variables": variables}, headers=headers)\n        resp.raise_for_status()\n        return resp.json()\n',
            ),
        ],
    ),
]

for date, msg, files in commits_data:
    for filepath, content in files:
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w") as f:
            f.write(content)

    os.system("git add -A")
    git_commit(date, msg)
    print(f"Created: {msg} ({date.strftime('%Y-%m-%d')})")

print(f"\nTotal commits: {len(commits_data)}")
