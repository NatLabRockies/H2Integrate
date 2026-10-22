"""Ocean alkalinity enhancement (OAE) powered by wind, with two cost modeling approaches.

- `offshore_plant_oae.yaml`: offshore wind and a battery power the OAE system, which uses
  `OAECostModel` and is included in a ProFAST levelized cost of CO2 calculation.
- `offshore_plant_oae_financials.yaml`: a smaller wind plant in Puget Sound powers the OAE system,
  which uses `OAECostAndFinancialModel` to estimate the carbon credit value needed for viability.
"""

import numpy as np

from h2integrate import H2IntegrateModel


##################################
# OAE with the OAE cost model and ProFAST finance
h2i_model = H2IntegrateModel("offshore_plant_oae.yaml")

# Set battery demand profile
# TODO: Update with demand module once it is developed
demand_profile = np.ones(8760) * 330.0
h2i_model.setup()
h2i_model.prob.set_val("battery.electricity_set_point", demand_profile, units="MW")

# Run the model
h2i_model.run()

# Post-process the results
h2i_model.post_process()

##################################
# OAE with the OAE cost and financial model
h2i_financials = H2IntegrateModel("offshore_plant_oae_financials.yaml")

h2i_financials.run()

h2i_financials.post_process()
