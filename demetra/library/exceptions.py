class DemetraError(Exception):
    pass


class SettingsError(DemetraError):
    pass


class EnvironmentConfigError(DemetraError):
    pass


class ProjectDoesNotExistsError(DemetraError):
    pass


class TrackerError(DemetraError):
    """Base error for issue-tracker backends (Linear, ClickUp).

    Transient by default: workflows retry on this class and give up only on
    :class:`TrackerConfigError`.
    """


class TrackerConfigError(TrackerError):
    """Permanent tracker misconfiguration; never retried."""


class LinearError(TrackerError):
    pass


class LinearConfigError(LinearError, TrackerConfigError):
    pass


class ClickUpError(TrackerError):
    pass


class ClickUpConfigError(ClickUpError, TrackerConfigError):
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


class PrDescriptionError(DemetraError):
    pass


class BuildError(DemetraError):
    pass


class PullRequestError(DemetraError):
    pass


class WikiError(DemetraError):
    pass


class AuthError(DemetraError):
    pass


class WaitlistedError(AuthError):
    def __init__(self, message: str = "Added to waitlist", *, entry_id: str | None = None) -> None:
        super().__init__(message)
        self.entry_id = entry_id
