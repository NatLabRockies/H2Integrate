from pathlib import Path

import numpy as np
import pandas as pd

from h2integrate.tools.run_cases import modify_tech_config, load_tech_config_cases
from h2integrate.core.h2integrate_model import H2IntegrateModel


# Create H2Integrate model
model = H2IntegrateModel("21_iron.yaml")

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
capexes = []
fopexes = []
vopexes = []

for casename in casenames:
    model = modify_tech_config(model, cases[casename])
    model.run()
    lcois.append(float(model.model.get_val("finance_subgroup_pig_iron.price_pig_iron")[0]))
    capexes.append(float(model.model.get_val("finance_subgroup_pig_iron.total_capex_adjusted")[0]))
    fopexes.append(float(model.model.get_val("finance_subgroup_pig_iron.total_opex_adjusted")[0]))
    vopexes.append(
        float(model.model.get_val("finance_subgroup_pig_iron.total_varopex_adjusted")[0])
    )

# Compare the Capex, Fixed Opex, and Variable Opex across the 4 cases
columns = [
    "Capex [Million USD]",
    "Fixed Opex [Million USD/year]",
    "Variable Opex [Million USD/year]",
    "LCOI [USD/kg]",
]
df = pd.DataFrame(
    np.transpose(np.vstack([capexes, fopexes, vopexes, lcois])), index=casenames, columns=columns
)
print(df)
