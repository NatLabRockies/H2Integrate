"""
Direct Ocean Capture Powered by Wind & Wave
===========================================

Short Description.

Longer Description.
"""

import numpy as np

from h2integrate import EXAMPLE_DIR, H2IntegrateModel


example_path = EXAMPLE_DIR / "09_co2/direct_ocean_capture"
h2i_model = H2IntegrateModel(example_path / "offshore_plant_doc.yaml")

# Set battery demand profile
# TODO: Update with demand module once it is developed
demand_profile = np.ones(8760) * 340.0
h2i_model.setup()
h2i_model.prob.set_val("battery.electricity_set_point", demand_profile, units="MW")

# Run the model
h2i_model.run()

# Post-process the results
h2i_model.post_process()
