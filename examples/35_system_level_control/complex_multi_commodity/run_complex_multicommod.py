import os

from h2integrate import EXAMPLE_DIR
from h2integrate.core.h2integrate_model import H2IntegrateModel


os.chdir(EXAMPLE_DIR / "35_system_level_control" / "complex_multi_commodity")

##################################
# Create an H2I model with a fixed electricity load demand
# h2i = H2IntegrateModel("top_level_config.yaml")

print("Starting V2 ...")
h2i = H2IntegrateModel("top_level_config_v2.yaml")

h2i.setup()

# Run the model
h2i.run()

print("Ran V2 successfully!")


print("Starting V1 ...")
h2i = H2IntegrateModel("top_level_config.yaml")

h2i.setup()

# Run the model
h2i.run()

print("Ran V1 successfully!")
# Post-process the results
# h2i.post_process()

# TODO: make even more complex by adding in an ammonia storage and combiner that goes to the demand tech
