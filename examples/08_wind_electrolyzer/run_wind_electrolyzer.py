import os
from pathlib import Path

import openmdao.api as om

from h2integrate.core.h2integrate_model import H2IntegrateModel


# change the current working directory to the example folder
os.chdir(Path(__file__).parent)

top_level_fpath = Path(__file__).parent / "wind_plant_electrolyzer.yaml"

# Create a GreenHEART model
h2i_model = H2IntegrateModel(top_level_fpath)

# Run the model
h2i_model.run()

# Post-process the results
h2i_model.post_process()

# Specify the filepath to the sql file, the folder and filename are in the driver_config
sql_fpath = Path(__file__).parent / "wind_electrolyzer" / "cases.sql"

# load the cases
cr = om.CaseReader(sql_fpath)

cases = list(cr.get_cases())

# theres only 1 case since we didnt run an optimization or design of experiments
case = cases[0]

# access values from a case similar to how we can access values from h2i_model.model
lcoh_custom = case.get_val("finance_subgroup_hydrogen.LCOH_produced_custom_model", units="USD/kg")
lcoh_profast = case.get_val("finance_subgroup_hydrogen.LCOH_produced_profast_model", units="USD/kg")
lcoe_profast = case.get_val("finance_subgroup_electricity_profast.LCOE", units="USD/MW/h")
lcoe_custom = case.get_val("finance_subgroup_electricity_custom.LCOE", units="USD/MW/h")

print(
    f"LCOH (USD/kg): is {lcoh_custom[0]:.2f} with custom model and "
    f"{lcoh_profast[0]:.2f} with ProFAST model"
)
print(
    f"LCOE (USD/MWh): is {lcoe_custom[0]:.2f} with custom model and "
    f"{lcoe_profast[0]:.2f} with ProFAST model"
)
