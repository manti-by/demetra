from demetra.library.exceptions import (
    AgentBudgetRetryError,
    AgentCompactionError,
    AgentContextOverflowError,
    AgentFailureError,
    AgentNetworkError,
    AgentPermissionError,
    AgentProviderError,
    AgentQuotaError,
    AgentRateLimitError,
)


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

WIKI_REQUIRED_SECTIONS: tuple[str, ...] = ("## TL;DR", "## Follow-ups", "## References")

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

NETWORK_ERROR_MARKERS: tuple[str, ...] = (
    "ECONNRESET",
    "ECONNREFUSED",
    "ETIMEDOUT",
    "ENOTFOUND",
    "EAI_AGAIN",
    "socket hang up",
)

AGENT_FAILURE_SIGNATURES: tuple[tuple[str, tuple[str, ...], type[AgentFailureError], bool], ...] = (
    (
        "budget_retry",
        ("requires more credits", "can only afford", "reduce max_tokens", "retry with fewer tokens"),
        AgentBudgetRetryError,
        True,
    ),
    (
        "quota_exhausted",
        (
            "insufficient credits",
            "credits exhausted",
            "monthly spending limit",
            "credit balance",
            "quota exceeded",
            "billing hard limit",
        ),
        AgentQuotaError,
        False,
    ),
    (
        "rate_limited",
        ("RATE_LIMIT", "rate limit exceeded", "too many requests", "HTTP 429", "429 Too Many Requests"),
        AgentRateLimitError,
        True,
    ),
    (
        "permission_denied",
        ("PERMISSION_DENIED", "permission denied", "403 Forbidden", "HTTP 403", "not authorized", "access denied"),
        AgentPermissionError,
        False,
    ),
    (
        "context_overflow",
        (
            "CONTEXT_LENGTH",
            "context length exceeded",
            "maximum context length",
            "prompt is too long",
            "input is too long",
        ),
        AgentContextOverflowError,
        False,
    ),
    (
        "compaction_unavailable",
        ("compaction unavailable", "compaction is not supported", "no compaction command"),
        AgentCompactionError,
        False,
    ),
    ("network_error", NETWORK_ERROR_MARKERS, AgentNetworkError, True),
    (
        "unknown_server_error",
        ("UnknownError", "Unexpected server error", "Internal server error", "HTTP 500", "500 Internal Server Error"),
        AgentProviderError,
        False,
    ),
)

AGENT_FAILURE_TYPE_CODES: dict[str, str] = {
    "InsufficientCredits": "quota_exhausted",
    "BudgetRetry": "budget_retry",
    "InFlightBudget": "budget_retry",
    "RateLimit": "rate_limited",
    "RateLimitExceeded": "rate_limited",
    "TooManyRequests": "rate_limited",
    "PermissionDenied": "permission_denied",
    "Forbidden": "permission_denied",
    "ContextLengthExceeded": "context_overflow",
    "ContextOverflow": "context_overflow",
    "CompactionUnavailable": "compaction_unavailable",
}
