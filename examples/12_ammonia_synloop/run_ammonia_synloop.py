from pathlib import Path

from h2integrate import H2IntegrateModel
from h2integrate.tools.run_cases import modify_tech_config, load_tech_config_cases


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
    model.run()
    model.post_process()
