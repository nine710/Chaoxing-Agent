"""Core business logic: window binding, viewport selection, screen capture,
mouse click, and the main state machine.

External callers should import submodules explicitly, e.g.::

    from chaoxing_agent.core.errors import FatalStopError
    from chaoxing_agent.core.state_machine import StateMachine

Why this ``__init__`` looks the way it does
-------------------------------------------
We deliberately avoid the self-import anti-pattern
(``from chaoxing_agent.core import (...)``), which short-circuits during
partially-initialized module imports.

We *also* avoid eagerly importing every submodule from here, because
``state_machine`` pulls in ``models.text_solver`` which in turn does
``from chaoxing_agent.core.errors``. If we imported ``state_machine``
first, the partially-initialized ``chaoxing_agent.core`` would have no
``errors`` attribute yet and the chain would fail.

So we only eagerly import the leaf submodules that do not pull in
``models``. The rest (notably ``state_machine`` and anything that
depends on it) are imported lazily by their consumers.
"""

# Leaf submodules — safe to import eagerly; they do not depend on
# ``models`` and therefore cannot form a cycle through this package.
import chaoxing_agent.core.click_executor as click_executor  # noqa: E402, F401
import chaoxing_agent.core.config_init as config_init  # noqa: E402, F401
import chaoxing_agent.core.coordinate_mapper as coordinate_mapper  # noqa: E402, F401
import chaoxing_agent.core.env_settings as env_settings  # noqa: E402, F401
import chaoxing_agent.core.errors as errors  # noqa: E402, F401
import chaoxing_agent.core.page_change_detector as page_change_detector  # noqa: E402, F401
import chaoxing_agent.core.screen_capture as screen_capture  # noqa: E402, F401
import chaoxing_agent.core.trace_logger as trace_logger  # noqa: E402, F401
import chaoxing_agent.core.viewport_selector as viewport_selector  # noqa: E402, F401
import chaoxing_agent.core.window_selector as window_selector  # noqa: E402, F401

# NOT eagerly imported to avoid a cycle:
#   state_machine  →  models.text_solver  →  chaoxing_agent.core.errors
# Importers should do ``from chaoxing_agent.core.state_machine import StateMachine``
# explicitly; Python will load the submodule on first access.

__all__ = [
    "click_executor",
    "config_init",
    "coordinate_mapper",
    "env_settings",
    "errors",
    "page_change_detector",
    "screen_capture",
    # "state_machine",  # imported lazily to break the models <-> core cycle
    "trace_logger",
    "viewport_selector",
    "window_selector",
]
