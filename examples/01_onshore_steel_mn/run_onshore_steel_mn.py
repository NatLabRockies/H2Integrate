import os
from pathlib import Path

import numpy as np

from h2integrate.core.h2integrate_model import H2IntegrateModel


os.chdir(Path(__file__).parent)

# Create a H2Integrate model
model = H2IntegrateModel("01_onshore_steel_mn.yaml")
# Set battery demand profile to electrolyzer capacity
demand_profile = np.ones(8760) * 720.0
# TODO: Update with demand module once it is developed
model.setup()
model.prob.set_val("battery.electricity_demand", demand_profile, units="MW")
# Run the model
model.run()

model.post_process()
