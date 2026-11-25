"""
Upstream Fixed Load Demand
==========================

Thumbnail Alt Text.

Longer Description.
"""

import os

from h2integrate import EXAMPLE_DIR, H2IntegrateModel


example_path = EXAMPLE_DIR / "35_system_level_control/upstream_demand"
os.chdir(example_path)

##################################
# Create an H2I model with a fixed electricity load demand
h2i = H2IntegrateModel(example_path / "upstream_demand.yaml")

h2i.setup()

# Run the model
h2i.run()

# Post-process the results
h2i.post_process()
