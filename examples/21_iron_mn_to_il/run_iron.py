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
lcois_ore = []
capexes_ore = []
fopexes_ore = []
vopexes_ore = []
lcois = []
capexes = []
fopexes = []
vopexes = []

for casename in casenames:
    model = modify_tech_config(model, cases[casename])
    model.run()
    model.post_process()
    lcois_ore.append(float(model.model.get_val("finance_subgroup_iron_ore.price_iron_ore")[0]))
    capexes_ore.append(
        float(model.model.get_val("finance_subgroup_iron_ore.total_capex_adjusted")[0])
    )
    fopexes_ore.append(
        float(model.model.get_val("finance_subgroup_iron_ore.total_opex_adjusted")[0])
    )
    vopexes_ore.append(
        float(model.model.get_val("finance_subgroup_iron_ore.total_varopex_adjusted")[0])
    )
    lcois.append(float(model.model.get_val("finance_subgroup_pig_iron.price_pig_iron")[0]))
    capexes.append(float(model.model.get_val("finance_subgroup_pig_iron.total_capex_adjusted")[0]))
    fopexes.append(float(model.model.get_val("finance_subgroup_pig_iron.total_opex_adjusted")[0]))
    vopexes.append(
        float(model.model.get_val("finance_subgroup_pig_iron.total_varopex_adjusted")[0])
    )

# Compare the Capex, Fixed Opex, and Variable Opex across the 4 cases
columns = [
    "LCO Iron Ore [USD/kg]",
    "Capex [Million USD]",
    "Fixed Opex [Million USD/year]",
    "Variable Opex [Million USD/year]",
]
df_ore = pd.DataFrame(
    np.transpose(np.vstack([capexes_ore, fopexes_ore, vopexes_ore, lcois_ore])),
    index=casenames,
    columns=columns,
)
print(df_ore)
columns[0] = "LCO Pig Iron [USD/kg]"
df = pd.DataFrame(
    np.transpose(np.vstack([capexes, fopexes, vopexes, lcois])), index=casenames, columns=columns
)
print(df)
