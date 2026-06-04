import numpy as np

from h2integrate import H2IntegrateModel


# Create a H2Integrate model
model = H2IntegrateModel("37_pem_fc.yaml")

# Setup the model
model.setup()

# Set fuel cell demand profile
demand_profile = np.ones(8760) * 20000
model.prob.set_val("h2_fuel_cell.electricity_set_point", demand_profile, units="kW")

# Run model
model.run()
model.post_process()
