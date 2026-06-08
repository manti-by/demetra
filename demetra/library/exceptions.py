class DemetraError(Exception):
    pass


class SettingsError(DemetraError):
    pass


class ProjectDoesNotExistsError(DemetraError):
    pass


class LinearError(DemetraError):
    pass


class InfiniteLoopError(DemetraError):
    pass


class UserCancelledError(DemetraError):
    pass


class AutoCancelledError(DemetraError):
    pass


class PlanError(DemetraError):
    pass


class BuildError(DemetraError):
    pass
