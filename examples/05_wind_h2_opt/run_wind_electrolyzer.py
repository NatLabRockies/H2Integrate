"""
Wind Plant Electrolysis
=======================

Thumbnail Alt Text.

Longer Description.
"""

from h2integrate import EXAMPLE_DIR, H2IntegrateModel


h2i = H2IntegrateModel(EXAMPLE_DIR / "05_wind_h2_opt/wind_plant_electrolyzer.yaml")

# Run the model
h2i.run()

h2i.post_process()
