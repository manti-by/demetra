"""Service layer package marker.

Individual services live in subpackages (e.g. ``auth``, ``linear``,
``clickup``, ``vcs``) whose ``__init__.py`` acts as the public facade;
``tracker`` dispatches between the ``linear`` and ``clickup`` backends. This
package contains no executable code.
"""
