import importlib
import importlib.abc
import importlib.machinery
import importlib.util
import sys
from collections.abc import Sequence
from types import ModuleType


_RELOCATED_MODULES: dict[str, str] = {
    "git": "demetra.services.vcs.git",
    "github": "demetra.services.vcs.github",
    "merge": "demetra.services.vcs.merge",
    "rebase": "demetra.services.vcs.rebase",
    "passwords": "demetra.services.auth.passwords",
    "allowlist": "demetra.services.auth.allowlist",
    "auth_copy": "demetra.services.auth.copy",
    "opencode": "demetra.services.agents.opencode",
    "cursor": "demetra.services.agents.cursor",
    "coderabbit": "demetra.services.agents.coderabbit",
    "groq": "demetra.services.llm.groq",
    "parser": "demetra.services.llm.parser",
    "prompt": "demetra.services.llm.prompt",
    "graphql": "demetra.services.linear.graphql",
    "oauth": "demetra.services.linear.oauth",
    "database": "demetra.services.persistence.database",
    "encryption": "demetra.services.persistence.encryption",
    "queue": "demetra.services.persistence.queue",
    "subprocess": "demetra.services.runtime.subprocess",
    "tui": "demetra.services.runtime.tui",
    "flow": "demetra.services.runtime.flow",
    "filesystem": "demetra.services.runtime.filesystem",
    "utils": "demetra.services.runtime.utils",
    "constants": "demetra.services.runtime.constants",
    "project": "demetra.services.runtime.project",
    "template": "demetra.services.runtime.template",
    "listener": "demetra.services.daemons.listener",
    "watcher": "demetra.services.daemons.watcher",
    "lint": "demetra.services.quality.lint",
    "test": "demetra.services.quality.test",
}


class _RelocatedLoader(importlib.abc.Loader):
    """Load a relocated module under its legacy import path."""

    def __init__(self, target: str) -> None:
        self._target = target

    def create_module(self, spec: importlib.machinery.ModuleSpec) -> ModuleType:
        return importlib.import_module(self._target)

    def exec_module(self, module: ModuleType) -> None:
        pass


class _RelocatedFinder(importlib.abc.MetaPathFinder):
    """Serve relocated modules under their legacy top-level names."""

    def find_spec(
        self,
        fullname: str,
        path: Sequence[str] | None = None,
        target: ModuleType | None = None,
    ) -> importlib.machinery.ModuleSpec | None:
        prefix = __name__ + "."
        if not fullname.startswith(prefix):
            return None
        short_name = fullname[len(prefix) :]
        relocated = _RELOCATED_MODULES.get(short_name)
        if relocated is None:
            return None
        return importlib.util.spec_from_loader(fullname, _RelocatedLoader(relocated))


sys.meta_path.insert(0, _RelocatedFinder())
