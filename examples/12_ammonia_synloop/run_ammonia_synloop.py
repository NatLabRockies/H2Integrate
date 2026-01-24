from pathlib import Path

import numpy as np

from h2integrate.tools.run_cases import modify_tech_config, load_tech_config_cases
from h2integrate.core.h2integrate_model import H2IntegrateModel


# Create a H2Integrate model
model = H2IntegrateModel("12_ammonia_synloop.yaml")

# Load cases
case_file = Path("hb_inputs.csv")
cases = load_tech_config_cases(case_file)

# Modify and run the model for different cases
caselist = [
    "Haber Bosch Big",
    "Haber Bosch Small",
]
for casename in caselist:
    case = cases[casename]
    model = modify_tech_config(model, case)
    # Set battery demand profile to electrolyzer capacity
    # TODO: Update with demand module once it is developed
    demand_profile = np.ones(8760) * 640.0
    model.setup()
    model.prob.set_val("battery.electricity_demand", demand_profile, units="MW")
    model.run()
    model.post_process()
