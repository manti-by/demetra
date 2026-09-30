SEARCH_STOP_WORDS: frozenset[str] = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "be",
        "been",
        "did",
        "do",
        "does",
        "for",
        "how",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "that",
        "the",
        "this",
        "to",
        "was",
        "were",
        "what",
        "why",
        "with",
    }
)

AGENT_HARNESSES: frozenset[str] = frozenset({"opencode", "claude"})

CLAUDE_EFFORT_LEVELS: frozenset[str] = frozenset({"low", "medium", "high", "xhigh", "max"})

# Explicit Linear MCP tool names, never a "mcp__linear__*" wildcard, so a new
# write tool added on the server side is never picked up automatically.
CLAUDE_LINEAR_READ_TOOLS: frozenset[str] = frozenset(
    {
        "mcp__linear__list_issues",
        "mcp__linear__get_issue",
        "mcp__linear__list_comments",
        "mcp__linear__list_projects",
        "mcp__linear__get_project",
        "mcp__linear__list_teams",
        "mcp__linear__get_team",
        "mcp__linear__list_users",
        "mcp__linear__get_user",
    }
)

CLAUDE_LINEAR_CREATE_TOOLS: frozenset[str] = frozenset(
    {
        "mcp__linear__create_issue",
        "mcp__linear__create_comment",
    }
)

PLAN_HEADER_STRING = "## Implementation Plan"
PLAN_IS_READY_STRING = "Ready to proceed to build."
PLAN_HAS_QUESTIONS = "Please check my questions above."

RESEARCH_HEADER_STRING = "## Research Report"

OS_ENV_ALLOWLIST: frozenset[str] = frozenset(
    {
        "PATH",
        "HOME",
        "USER",
        "LOGNAME",
        "SHELL",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "TZ",
        "TERM",
        "PWD",
        "VIRTUAL_ENV",
        "UV_PROJECT_ENVIRONMENT",
        "UV_PYTHON",
        # SSH agent / git-over-SSH auth required by credential-bearing git and
        # gh commands; without these every clone/fetch/push would silently fail.
        "SSH_AUTH_SOCK",
        "SSH_AGENT_PID",
        "GIT_SSH_COMMAND",
        # Proxy variables so outbound clone/fetch/push and gh API calls keep
        # working behind a proxy.
        "http_proxy",
        "https_proxy",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "NO_PROXY",
        "no_proxy",
        "all_proxy",
        "ALL_PROXY",
    }
)
