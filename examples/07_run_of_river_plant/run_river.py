"""
Run of River Hydropower
=======================

Short Description.

Longer Description.
"""

import os

from h2integrate import EXAMPLE_DIR, H2IntegrateModel


example_path = EXAMPLE_DIR / "07_run_of_river_plant"
os.chdir(example_path)

# Create an H2I model
h2i = H2IntegrateModel(example_path / "07_run_of_river.yaml")

# Run the model
h2i.run()

# Post-process the results
h2i.post_process()
