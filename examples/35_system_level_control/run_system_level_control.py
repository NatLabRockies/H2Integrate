"""
System-Level Control Example: Wind + Battery + Grid
====================================================

This example demonstrates the ``system_level_control`` configuration section
in H2Integrate. A wind farm provides intermittent electricity, a battery
stores excess production, and grid purchases fill any remaining demand gap.

The ``system_level_control`` section in ``plant_config.yaml`` declares:
  - **wind** as a ``fixed`` producer (output follows the wind resource)
  - **grid_buy** as a ``dispatchable`` producer (can provide up to its limit)
  - **battery** as ``storage``
  - **electrical_load_demand** as a ``demand``

At initialization, H2Integrate automatically:
  1. Validates that all referenced technologies exist
  2. Adds a standalone ``SystemLevelController`` component to the plant group
  3. Wires the controller to read wind production and output battery dispatch

The controller uses simple heuristic dispatch: excess wind charges the
battery, and the battery discharges when wind is insufficient. Any remaining
gap flows to the grid through the existing ``technology_interconnections``.

Usage:
    python run_system_level_control.py

Note: Requires wind resource data access (NREL Wind Toolkit API key).
"""

from pathlib import Path

from h2integrate.core.h2integrate_model import H2IntegrateModel


config_path = Path(__file__).parent / "system_level_control.yaml"

h2i = H2IntegrateModel(str(config_path))
h2i.run()
h2i.post_process()
