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


class AgentNetworkError(DemetraError):
    def __init__(self, agent: str, stderr: str) -> None:
        super().__init__(f"Agent '{agent}' failed with a network error: {stderr.strip() or 'unknown error'}")
        self.agent = agent
        self.stderr = stderr


class AuthError(DemetraError):
    pass


class WaitlistedError(AuthError):
    def __init__(self, message: str = "Added to waitlist", *, entry_id: str | None = None) -> None:
        super().__init__(message)
        self.entry_id = entry_id
