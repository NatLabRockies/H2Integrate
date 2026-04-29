"""Backward-compatible alias for :class:`DemandFollowingControl`.

The ``SystemLevelControl`` name is kept so that existing imports
(e.g. ``from ...system_level_control import SystemLevelControl``)
continue to work.  New code should import the specific controller
class directly.
"""

from h2integrate.control.control_strategies.system_level.demand_following_control import (  # noqa: F401
    DemandFollowingControl as SystemLevelControl,
)
