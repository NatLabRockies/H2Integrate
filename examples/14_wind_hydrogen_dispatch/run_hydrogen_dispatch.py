"""
Hydrogen Dispatch Open-Loop Controller
======================================

Example script for running the base example in the hydrogren dispatch open-loop controller example.
"""

from h2integrate import EXAMPLE_DIR, H2IntegrateModel


config_file = (
    EXAMPLE_DIR / "14_wind_hydrogen_dispatch/inputs/h2i_wind_to_h2_storage.yaml"
).resolve()
model = H2IntegrateModel(config_file)
model.run()
model.post_process()
