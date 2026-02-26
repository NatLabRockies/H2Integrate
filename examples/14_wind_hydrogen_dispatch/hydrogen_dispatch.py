"""Example script for running the base example in the hydrogren dispatch open-loop controller
example.
"""

from pathlib import Path

from h2integrate.core.h2integrate_model import H2IntegrateModel


config_file = Path("./inputs/h2i_wind_to_h2_storage.yaml").resolve()
model = H2IntegrateModel(config_file)
model.run()
model.post_process()
