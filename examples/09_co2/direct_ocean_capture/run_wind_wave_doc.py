import numpy as np

from h2integrate.core.h2integrate_model import H2IntegrateModel


# Create a GreenHEART model
h2i_model = H2IntegrateModel("offshore_plant_doc.yaml")

# Set battery demand profile
# TODO: Update with demand module once it is developed
demand_profile = np.ones(8760) * 340.0
h2i_model.setup()
h2i_model.prob.set_val("battery.electricity_demand", demand_profile, units="MW")

# Run the model
h2i_model.run()

# Post-process the results
h2i_model.post_process()
