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
