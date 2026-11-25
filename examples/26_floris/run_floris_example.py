"""
FLORIS Wind Plant
=================

Thumbnail Alt Text.

Longer Description.
"""

import os

from h2integrate import EXAMPLE_DIR, H2IntegrateModel, load_yaml


example_path = EXAMPLE_DIR / "26_floris"
os.chdir(example_path)

driver_config = load_yaml(example_path / "driver_config.yaml")
tech_config = load_yaml(example_path / "tech_config.yaml")
plant_config = load_yaml(example_path / "plant_config.yaml")

h2i_config = {
    "name": "H2Integrate_config",
    "system_summary": "",
    "driver_config": driver_config,
    "technology_config": tech_config,
    "plant_config": plant_config,
}
# Create a H2I model
h2i = H2IntegrateModel(h2i_config)

# Run the model
h2i.run()

h2i.post_process()
