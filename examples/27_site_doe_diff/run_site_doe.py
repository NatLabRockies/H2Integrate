"""
Site Design Sweep
=================

Short Description.

Longer Description.
"""

import os

import pandas as pd
import openmdao.api as om

from h2integrate import EXAMPLE_DIR, H2IntegrateModel


example_path = EXAMPLE_DIR / "27_site_doe_diff"
os.chdir(example_path)

# Create an H2I model
h2i = H2IntegrateModel(example_path / "27_wind_solar_site_doe.yaml")

# Run the model
h2i.run()

# Post-process the results
h2i.post_process(summarize_sql=True)

# Specify the filepath to the sql file, the folder and filename are in the driver_config
sql_fpath = example_path / "ex_27_out" / "cases.sql"

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
