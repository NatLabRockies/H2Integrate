import os
from pathlib import Path

import pandas as pd
import openmdao.api as om

from h2integrate.core.h2integrate_model import H2IntegrateModel


os.chdir(Path(__file__).parent)

# Create an H2I model
h2i = H2IntegrateModel("23_wind_solar_site_doe.yaml")

# Run the model
h2i.run()

# Post-process the results
h2i.post_process(summarize_sql=True)

# Specify the filepath to the sql file, the folder and filename are in the driver_config
sql_fpath = Path(__file__).parent / "ex_23_out" / "cases.sql"

# load the cases
cr = om.CaseReader(sql_fpath)

cases = list(cr.get_cases())

dv_df = pd.DataFrame()
# iterate through cases and get the design variables and object
for ci, case in enumerate(cases):
    design_vars = case.get_design_vars()
    objectives = case.get_objectives()
    dv_df = pd.concat([pd.DataFrame(design_vars, index=[ci]), dv_df], axis=0)

print(f"{len(dv_df)} cases run, {len(dv_df.drop_duplicates())} unique cases")
