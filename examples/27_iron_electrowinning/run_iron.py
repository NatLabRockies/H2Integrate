"""Comparing three different iron electrowinning technologies

This script runs an end-to-end iron production system (including the mine) and compareds the
levelized cost of sponge_iron across three different iron electrowinning technologies to see
how their costs compare:
    - Aqueous Hydroxide Electrolysis (AHE)
    - Molten Salt Electrolysis (MSE)
    - Molten Oxide Electrolysis (MOE)

New users may find it helpful to look at the tech_config.yaml (particularly the iron_plant) to see
how the technologies were set up, as well as the  plant_config.yaml (particularly the
technology_interconnections) to see how the technologies were connected.

"""

from pathlib import Path

from h2integrate.tools.run_cases import modify_tech_config, load_tech_config_cases
from h2integrate.core.h2integrate_model import H2IntegrateModel


# Create H2Integrate model
model = H2IntegrateModel("27_iron_electrowinning.yaml")

# Load cases
case_file = Path("test_inputs.csv")
cases = load_tech_config_cases(case_file)

# Modify and run the model for different cases
casenames = [
    "AHE",
    "MSE",
    "MOE",
]
lcois = []

for casename in casenames:
    model = modify_tech_config(model, cases[casename])
    model.run()
    model.post_process()
    lcois.append(float(model.model.get_val("finance_subgroup_sponge_iron.price_sponge_iron")[0]))

# Compare the LCOIs from each electrowinning type
print(lcois)
