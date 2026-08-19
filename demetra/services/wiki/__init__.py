import logging
import re

from demetra.library.models import Context, LinearTask
from demetra.services.llm.openrouter import summarize_session
from demetra.services.runtime.subprocess import run_command
from demetra.services.wiki.facts import (
    budget_exceeded,
    collect_session_facts,
    git_default_branch,
    git_diff_facts,
    session_log_tail,
)
from demetra.services.wiki.index import (
    cluster_for,
    find_topic_cluster,
    index_entry,
    insert_cluster_entry,
    insert_pages_entry,
    patch_index,
    prune_index_pages,
    read_index,
    regenerate_by_topic,
    write_index,
)
from demetra.services.wiki.maintenance import (
    answer_sweep,
    check_agents_drift,
    commit_revalidation,
    dedup_pages,
    has_answer,
    merge_page_content,
    on_default_branch,
    page_tokens,
    pick_survivor,
    revalidate_wiki_and_agents,
    revalidation_changed_files,
    run_wiki_revalidation,
    similarity,
)
from demetra.services.wiki.naming import infer_services, infer_tags, session_filename, today
from demetra.services.wiki.parsing import existing_page_for_ticket, page_date, parse_frontmatter, parse_page_file
from demetra.services.wiki.render import (
    dump_frontmatter,
    render_wiki_page,
    truncate,
    write_page,
    write_session_wiki_page,
)
from demetra.settings import (
    BASE_PATH,
    GIT,
    LOG_DIR,
    WIKI,
)


logger = logging.getLogger(__name__)

WIKI_ROOT = (BASE_PATH / "wiki").resolve()
PAGES_ROOT = WIKI_ROOT / "pages"

FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
BARE_DASH_RE = re.compile(r"^(\s*[A-Za-z_][\w]*\s*:\s*)-$", re.MULTILINE)
PAGE_LINK_RE = re.compile(r"\]\(pages/([^)]+)\)")

PAGE_TYPE = "implementation"
PAGE_STATUS = "resolved"

LOG_TAIL_LINES = 200

INDEX_PATH = WIKI_ROOT / "INDEX.md"
QUESTIONS_PATH = WIKI_ROOT / "QUESTIONS.md"
AGENTS_PATH = BASE_PATH / "AGENTS.md"

AGENTS_DRIFT_ANCHORS = (
    "demetra/services/wiki.py",
    "demetra/tools/wiki.py",
    "uv.lock",
    "Linear",
    "GitHub",
    "Groq",
    "OpenRouter",
    "never prefix with",
)

DEDUP_SIMILARITY_THRESHOLD = 0.85

TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Workflow orchestration & agents": (
        "workflow",
        "plan",
        "build",
        "review",
        "agent",
        "resolve",
        "question",
        "opencode",
    ),
    "Sessions, status & resume": ("session", "status", "resume", "step", "history", "websocket"),
    "React frontend / UI": ("react", "frontend", "ui", "component", "vite", "favicon"),
    "Linear & GitHub integrations": ("linear", "github", "pr", "notification", "listener", "oauth"),
    "Authentication & API security": ("auth", "password", "cookie", "cors", "jwt", "bcrypt", "security"),
    "Database & migrations": ("database", "migration", "sqlalchemy", "postgres", "alembic"),
    "Context, tokens & compaction": ("context", "token", "compaction", "compression"),
    "Logging infrastructure": ("log", "ansi", "logging"),
    "MCP / integrations": ("mcp", "tool", "wiki"),
    "Testing & tooling": ("test", "pytest", "ruff", "lint", "feature flag"),
    "Docs, feature flags & release tooling": ("agents.md", "docs", "release", "version", "flag"),
    "Deploy & infrastructure": ("deploy", "systemd", "nginx", "docker", "infrastructure"),
    "Subprocess & timeouts": ("subprocess", "timeout", "shell"),
    "Git & worktrees": ("git", "worktree", "branch", "merge", "rebase"),
    "TUI & CLI": ("tui", "cli", "terminal", "rich"),
}

REVALIDATION_RETRYABLE = "__wiki_revalidation_retryable__"

__all__ = [
    "AGENTS_DRIFT_ANCHORS",
    "AGENTS_PATH",
    "BARE_DASH_RE",
    "BASE_PATH",
    "DEDUP_SIMILARITY_THRESHOLD",
    "FRONTMATTER_RE",
    "GIT",
    "INDEX_PATH",
    "LOG_DIR",
    "LOG_TAIL_LINES",
    "PAGES_ROOT",
    "PAGE_LINK_RE",
    "PAGE_STATUS",
    "PAGE_TYPE",
    "QUESTIONS_PATH",
    "REVALIDATION_RETRYABLE",
    "TOPIC_KEYWORDS",
    "WIKI",
    "WIKI_ROOT",
    "Context",
    "LinearTask",
    "answer_sweep",
    "budget_exceeded",
    "check_agents_drift",
    "cluster_for",
    "collect_session_facts",
    "commit_revalidation",
    "dedup_pages",
    "dump_frontmatter",
    "existing_page_for_ticket",
    "find_topic_cluster",
    "git_default_branch",
    "git_diff_facts",
    "has_answer",
    "index_entry",
    "infer_services",
    "infer_tags",
    "insert_cluster_entry",
    "insert_pages_entry",
    "merge_page_content",
    "on_default_branch",
    "page_date",
    "page_tokens",
    "parse_frontmatter",
    "parse_page_file",
    "patch_index",
    "pick_survivor",
    "prune_index_pages",
    "read_index",
    "regenerate_by_topic",
    "render_wiki_page",
    "revalidate_wiki_and_agents",
    "revalidation_changed_files",
    "run_command",
    "run_wiki_revalidation",
    "session_filename",
    "session_log_tail",
    "similarity",
    "summarize_session",
    "today",
    "truncate",
    "write_index",
    "write_page",
    "write_session_wiki_page",
]
