from h2integrate.core.h2integrate_model import H2IntegrateModel
from h2integrate.postprocess.sql_timeseries_to_csv import save_case_timeseries_as_csv


# Create a H2Integrate model
h2i = H2IntegrateModel("02_texas_ammonia.yaml")

# Run the model
h2i.run()

h2i.post_process()

# Save all timeseries data to a csv file
timeseries_data = save_case_timeseries_as_csv(h2i.recorder_path, save_to_file=True)

# Get a subset of timeseries data and don't save it to a csv file
vars_to_save = [
    "electrolyzer.hydrogen_out",
    "hopp.electricity_out",
    "ammonia.ammonia_out",
    "h2_storage.hydrogen_out",
]
timeseries_data = save_case_timeseries_as_csv(
    h2i.recorder_path, vars_to_save=vars_to_save, save_to_file=False
)
