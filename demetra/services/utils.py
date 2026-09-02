import logging
import time
from collections import deque

from sqlalchemy.exc import SQLAlchemyError

from demetra.settings import AUTH_RATE_LIMIT_MAX, AUTH_RATE_LIMIT_WINDOW


logger = logging.getLogger(__name__)


async def mark_waitlist_joined_safe(entry_type: str, value: str) -> None:
    """Mark a waitlist entry as joined without ever failing the calling flow.

    The audit write happens after the user account and session already exist,
    so a database failure here must not turn a successful login or signup
    into an error response.

    Args:
        entry_type: The entry type, ``"email"`` or ``"github_username"``.
        value: The raw value to normalize and match.
    """
    # Local import: demetra.services.auth.sessions imports this module, so a
    # module-level import of the auth waitlist service would be circular.
    from demetra.services.auth.waitlist import mark_waitlist_joined_by_value

    try:
        await mark_waitlist_joined_by_value(entry_type=entry_type, value=value)
    except SQLAlchemyError:
        logger.warning("Failed to mark waitlist joined for %s=%s", entry_type, value, exc_info=True)


class RateLimiter:
    """In-process sliding-window rate limiter keyed by an opaque client key.

    Memory is bounded by pruning expired windows on every check; events are
    only recorded for allowed calls, so a denied key gets exactly
    ``max_events`` attempts per window.
    """

    def __init__(self, max_events: int, window_seconds: int) -> None:
        self.max_events = max_events
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = {}

    def is_allowed(self, key: str) -> bool:
        """Return whether the key may perform an event, recording it when allowed.

        Args:
            key: Opaque client identifier, e.g. the request IP.

        Returns:
            bool: True when the event is within the limiter budget.
        """
        now = time.monotonic()
        events = self._events.get(key)
        if events is not None:
            while events and events[0] <= now - self.window_seconds:
                events.popleft()
            if not events:
                del self._events[key]
                events = None
        if events is None:
            self._events[key] = deque([now])
            return True
        if len(events) >= self.max_events:
            return False
        events.append(now)
        return True


auth_rate_limiter = RateLimiter(max_events=AUTH_RATE_LIMIT_MAX, window_seconds=AUTH_RATE_LIMIT_WINDOW)
