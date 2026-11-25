"""
Wind Plant Paper Production
===========================

Short Description.

Longer Description.
"""

from h2integrate import EXAMPLE_DIR, H2IntegrateModel


h2i = H2IntegrateModel(EXAMPLE_DIR / "06_custom_tech/wind_plant_paper.yaml")

# Run the model
h2i.run()

h2i.post_process()
