"""
Site-Based Design of Experiments
================================

Short Description.

Longer Description.
"""

import os

import openmdao.api as om

from h2integrate import EXAMPLE_DIR, H2IntegrateModel


example_path = EXAMPLE_DIR / "22_site_doe"
os.chdir(example_path)

# Create an H2I model
h2i = H2IntegrateModel(example_path / "22_solar_site_doe.yaml")

# Run the model
h2i.run()

# Post-process the results, save the .sql results to a .csv file
h2i.post_process(summarize_sql=False)

# Specify the filepath to the sql file, the folder and filename are in the driver_config
sql_fpath = example_path / "ex_22_out" / "cases.sql"

# load the cases
cr = om.CaseReader(sql_fpath)

cases = list(cr.get_cases())

# iterate through cases and get the design variables and object
for ci, case in enumerate(cases):
    design_vars = case.get_design_vars()
    objectives = case.get_objectives()
    print(f"Case {ci}:")
    print(f"\t design variables: {design_vars}")
    print(f"\t objectives: {objectives}")
