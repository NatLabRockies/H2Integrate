"""Minimal working example from the DOE user guide docs."""

from h2integrate.core.utilities import load_yaml, check_file_format_for_csv_generator
from h2integrate.core.dict_utils import update_defaults
from h2integrate.core.h2integrate_model import H2IntegrateModel


# Load the configurations and run the model
config = load_yaml("20_solar_electrolyzer_doe.yaml")

driver_config = load_yaml(config["driver_config"])
csv_config_fn = driver_config["driver"]["design_of_experiments"]["filename"]

try:
    model = H2IntegrateModel(config)
    model.run()
except UserWarning as e:
    print(f"Caught UserWarning: {e}")

"""
To fix the issue with the UserWarning, we'll take the following steps to try and fix
the bug in our CSV file:
1. Run the `check_file_format_for_csv_generator` method mentioned in the UserWarning
  and create a new csv file that is hopefully free of errors
2. Make a new driver config file that has "filename" point to the new csv file created
  in Step 1.
3. Make a new top-level config file that points to the updated driver config file
  created in Step 2.
"""

# Step 1
new_csv_filename = check_file_format_for_csv_generator(
    csv_config_fn,
    driver_config,
    check_only=False,
    overwrite_file=False,
)

# Step 2
updated_driver = update_defaults(
    driver_config["driver"],
    "filename",
    new_csv_filename.name,
)
driver_config["driver"].update(updated_driver)
print(f"New DOE driver CSV file: {new_csv_filename}")

# Step 3
config["driver_config"] = driver_config

# Rerun the model
model = H2IntegrateModel(config)
model.run()
