import numpy as np

from h2integrate.core.h2integrate_model import H2IntegrateModel


# Create a H2Integrate model
model = H2IntegrateModel("02_texas_ammonia.yaml")
# Set battery demand profile to electrolyzer capacity
# TODO: Update with demand module once it is developed
demand_profile = np.ones(8760) * 640.0
model.setup()
model.prob.set_val("battery.electricity_demand", demand_profile, units="MW")
# Run the model
model.run()

model.post_process()
