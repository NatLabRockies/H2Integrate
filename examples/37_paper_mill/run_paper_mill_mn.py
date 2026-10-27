"""Run script for the paper mill example (Minnesota site).

Sets up, runs, and post-processes the H2Integrate paper mill model, then exports
results to CSV using the built-in SQL postprocessing utilities:

- Scalar outputs are saved via ``convert_sql_to_csv_summary``.
- Timeseries profiles are saved via ``save_case_timeseries_as_csv``.

Both CSV files are written to the ``outputs/`` directory alongside the SQL recorder file.
"""

import os
from pathlib import Path

from h2integrate.core.h2integrate_model import H2IntegrateModel
from h2integrate.postprocess.sql_to_csv import convert_sql_to_csv_summary
from h2integrate.postprocess.sql_timeseries_to_csv import save_case_timeseries_as_csv


this_dir = Path(__file__).parent
os.chdir(this_dir)

model = H2IntegrateModel("37_paper_mill_mn.yaml")

model.setup()
model.run()
model.post_process()

sql_fpath = this_dir / "outputs" / "cases.sql"

convert_sql_to_csv_summary(sql_fpath)
save_case_timeseries_as_csv(sql_fpath)
