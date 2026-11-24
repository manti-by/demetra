class DemetraError(Exception):
    pass


class SettingsError(DemetraError):
    pass


class EnvironmentConfigError(DemetraError):
    pass


class ProjectDoesNotExistsError(DemetraError):
    pass


class LinearError(DemetraError):
    pass


class LinearConfigError(LinearError):
    pass


class InfiniteLoopError(DemetraError):
    pass


class UserCancelledError(DemetraError):
    pass


class AutoCancelledError(DemetraError):
    pass


class AwaitingInputError(DemetraError):
    """The task could not be parked in Awaiting Input, so the run stops without
    moving the ticket: it stays in its current column for manual recovery, and
    the saved build plan is discarded so a later run replans instead of building
    from the answers to questions that were never answered.
    """


class PlanError(DemetraError):
    pass


class ReviewError(DemetraError):
    pass


class LintError(DemetraError):
    pass


class PrDescriptionError(DemetraError):
    pass


class BuildError(DemetraError):
    pass


class PullRequestError(DemetraError):
    pass


class WikiError(DemetraError):
    pass


class OpenCodeError(DemetraError):
    pass


class OpenCodeCLIError(OpenCodeError):
    pass


class AgentFailureError(DemetraError):
    """A non-zero agent exit whose provider output matched a known failure class.

    ``stderr`` is redacted before an instance is built, so every rendered comment
    and history row is safe to show to a human. ``retryable`` and ``template`` are
    class-level defaults; the classifier may override ``code`` per signature.
    """

    code = "agent_failure"
    template = "agent_provider_failed"
    retryable = False

    def __init__(
        self,
        agent: str,
        stderr: str,
        *,
        code: str | None = None,
        retry_after_ms: int | None = None,
    ) -> None:
        self.agent = agent
        self.stderr = stderr
        self.code = code or type(self).code
        self.retry_after_ms = retry_after_ms
        super().__init__(self._message())

    def _message(self) -> str:
        return f"Agent '{self.agent}' failed ({self.code}): {self.stderr.strip() or 'unknown error'}"


class AgentQuotaError(AgentFailureError):
    code = "quota_exhausted"
    template = "agent_quota_failed"


class AgentBudgetRetryError(AgentFailureError):
    code = "budget_retry"
    template = "agent_budget_retry_failed"
    retryable = True


class AgentRateLimitError(AgentFailureError):
    code = "rate_limited"
    template = "agent_rate_limit_failed"
    retryable = True


class AgentPermissionError(AgentFailureError):
    code = "permission_denied"
    template = "agent_permission_failed"


class AgentContextOverflowError(AgentFailureError):
    code = "context_overflow"
    template = "agent_context_overflow_failed"


class AgentProviderError(AgentFailureError):
    code = "unknown_server_error"
    template = "agent_provider_failed"


class AgentCompactionError(AgentFailureError):
    code = "compaction_unavailable"
    template = "agent_compaction_failed"


class AgentNetworkError(AgentFailureError):
    code = "network_error"
    template = "agent_network_failed"
    retryable = True

    def _message(self) -> str:
        return f"Agent '{self.agent}' failed with a network error: {self.stderr.strip() or 'unknown error'}"


class AuthError(DemetraError):
    pass


class WaitlistedError(AuthError):
    def __init__(self, message: str = "Added to waitlist", *, entry_id: str | None = None) -> None:
        super().__init__(message)
        self.entry_id = entry_id
