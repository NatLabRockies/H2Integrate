from pathlib import Path

from h2integrate.tools.run_cases import modify_tech_config, load_tech_config_cases
from h2integrate.core.h2integrate_model import H2IntegrateModel


# Create H2Integrate models - comparing old and new
model = H2IntegrateModel("21_iron.yaml")
model_old = H2IntegrateModel("21_iron_old.yaml")

# Load cases
case_file = Path("test_inputs.csv")
cases = load_tech_config_cases(case_file)

# Modify and run the model for different cases
casenames = [
    "Case 1",
    "Case 2",
    "Case 3",
    "Case 4",
]
lcois = []
lcois_old = []

for casename in casenames:
    model = modify_tech_config(model, cases[casename])
    model_old = modify_tech_config(model_old, cases[casename])
    model.run()
    model_old.run()
    model.post_process()
    model_old.post_process()
    lcois.append(float(model.model.get_val("finance_subgroup_pig_iron.price_pig_iron")[0]))
    lcois_old.append(float(model_old.model.get_val("finance_subgroup_pig_iron.price_pig_iron")[0]))

# Compare the LCOIs from iron_wrapper and modular iron
print(lcois)
print(lcois_old)
