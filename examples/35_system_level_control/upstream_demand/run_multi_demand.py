import os

from h2integrate import EXAMPLE_DIR
from h2integrate.core.h2integrate_model import H2IntegrateModel


os.chdir(EXAMPLE_DIR / "35_system_level_control" / "upstream_demand")

##################################
# Create an H2I model with a fixed electricity load demand
h2i = H2IntegrateModel("upstream_demand.yaml")

h2i.setup()

# Run the model
h2i.run()

# Post-process the results
h2i.post_process()
