"""Example of an iron mine sending processed ore pellets to a separate DRI iron plant and EAF

In this example, iron ore pellets are produced at different iron mine locations in NE Minnesota.
These mines send processed ore pellets to a separate iron DRI plant located outside Chicago.
Four different cases are generated for four different iron mine setups in the `test_inputs.csv`.
The first two cases generate standard blast furnace gradepellets at two different mine locations.
The second two cases generate DR grade pellets at the same location, with the output capacity
varied to show how the capacity of the mine does not affect the levelized cost of iron_ore pellets
(LCOI), nor does it affect the final cost of the pig_iron produced by DRI (LCOP) or the cost of the
steel produced by the EAF (LCOS).

"""

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
    "Standard Iron - Hibbing",
    "Standard Iron - Northshore",
    "DR Grade Iron - Northshore",
    "DR Grade Iron - Northshore (adjusted)",
]

# Create empty lists to store the costs
lcois_ore = []
capexes_ore = []
fopexes_ore = []
vopexes_ore = []
production_ore = []
lcois_iron = []
capexes_iron = []
fopexes_iron = []
vopexes_iron = []
production_ore = []
lcois_steel = []
capexes_steel = []
fopexes_steel = []
vopexes_steel = []

model.run()
model.post_process()

for casename in casenames:
    model = modify_tech_config(model, cases[casename])
    model.run()
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
    lcois_iron.append(float(model.model.get_val("finance_subgroup_pig_iron.price_pig_iron")[0]))
    capexes_iron.append(
        float(model.model.get_val("finance_subgroup_pig_iron.total_capex_adjusted")[0])
    )
    fopexes_iron.append(
        float(model.model.get_val("finance_subgroup_pig_iron.total_opex_adjusted")[0])
    )
    vopexes_iron.append(
        float(model.model.get_val("finance_subgroup_pig_iron.total_varopex_adjusted")[0])
    )
    lcois_steel.append(float(model.model.get_val("finance_subgroup_steel.price_steel")[0]))
    capexes_steel.append(
        float(model.model.get_val("finance_subgroup_steel.total_capex_adjusted")[0])
    )
    fopexes_steel.append(
        float(model.model.get_val("finance_subgroup_steel.total_opex_adjusted")[0])
    )
    vopexes_steel.append(
        float(model.model.get_val("finance_subgroup_steel.total_varopex_adjusted")[0])
    )

# Compare the Capex, Fixed Opex, and Variable Opex across the 4 cases
columns = pd.MultiIndex.from_tuples(
    [
        ("Levelized Cost", "[USD/kg]"),
        ("Capex", "[USD]"),
        ("Fixed Opex", "[USD/year]"),
        ("Variable Opex", "[USD/year]"),
    ]
)
print()

df_ore = pd.DataFrame(
    np.transpose(np.vstack([lcois_ore, capexes_ore, fopexes_ore, vopexes_ore])),
    index=casenames,
    columns=columns,
)
print(df_ore)

print()
df_iron = pd.DataFrame(
    np.transpose(np.vstack([lcois_iron, capexes_iron, fopexes_iron, vopexes_iron])),
    index=casenames,
    columns=columns,
)
print(df_iron)

print()
df_steel = pd.DataFrame(
    np.transpose(np.vstack([lcois_steel, capexes_steel, fopexes_steel, vopexes_steel])),
    index=casenames,
    columns=columns,
)
df_steel = df_steel.iloc[2:]
print(df_steel)
