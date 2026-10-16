"""Filesystem roots the MCP tools read from.

Every project-specific path the tools reach for is resolved here, so the tool
modules stay free of path derivation and each root can be overridden in one
place. Tuning values (``SEARCH``) live in :mod:`demetra.settings`.
"""

from demetra.settings import BASE_PATH, LOG_DIR


PROJECT_ROOT = BASE_PATH

# The importable package the docstring tool indexes.
SOURCE_ROOT = PROJECT_ROOT / "demetra"

LOG_ROOT_DISPLAY = str(LOG_DIR)

# Resolved separately: on macOS /var is a symlink to /private/var, and the
# path-containment checks require a fully resolved root on both sides.
LOG_ROOT_RESOLVED = LOG_DIR.resolve()
