import time
import pprint
from copy import deepcopy
from pathlib import Path

import yaml

from h2integrate import H2IntegrateModel, load_tech_yaml, load_plant_yaml, load_driver_yaml
from h2integrate.core.dict_utils import percent_diff_dicts, find_nonzero_percent_diffs


# Run one or both simulation paradigms by changing the flags in this dict
run_dict = {
    "run_sequential": True,
    "run_time_marching": True,
}

# Load config files into dict
config_root = Path(__file__).parent
config_path = config_root / "solar_battery_grid.yaml"

# Load top level config
with Path(config_path).open() as f:
    config = yaml.safe_load(f)

config["driver_config"] = load_driver_yaml(config_root / config["driver_config"])
config["technology_config"] = load_tech_yaml(config_root / config["technology_config"])
config["plant_config"] = load_plant_yaml(config_root / config["plant_config"])

# Run simulation sequentially one subsystem at a time
if run_dict.get("run_sequential", False):
    config_seq = deepcopy(config)
    config_seq["plant_config"]["plant"]["simulation"].pop("n_timesteps_window")

    # Create an H2I model for standard year-long simulation
    h2i_seq = H2IntegrateModel(config_seq)

    t0 = time.time()
    # Run the model
    h2i_seq.run()
    t1 = time.time()

    print(f"Sequential took {t1 - t0:.3f} seconds")

    # Post-process the results
    h2i_seq.post_process(print_results=False)

    inputs_seq = dict(h2i_seq.model.list_inputs(out_stream=None))
    outputs_seq = dict(h2i_seq.model.list_outputs(out_stream=None))

    lcoe_seq = outputs_seq[
        "plant.finance_subgroup_renewables.electricity_finance_profast_model.LCOE"
    ]


# Run the time-marching simulation, advancing all subsystems one window of timesteps at a time
if run_dict.get("run_time_marching", False):
    config_tm = deepcopy(config)

    config_tm["plant_config"]["plant"]["simulation"]["n_timesteps"] = 8760
    config_tm["plant_config"]["plant"]["simulation"]["n_timesteps_window"] = 24

    # Create an H2I model for time-marching simulation
    h2i_tm = H2IntegrateModel(config_tm)

    t0 = time.time()
    # Run the model
    h2i_tm.run()
    t1 = time.time()

    print(f"Time-marching took {t1 - t0:.3f} seconds")

    # Post-process the results
    h2i_tm.post_process(print_results=False)

    inputs_tm = dict(h2i_tm.model.list_inputs(out_stream=None))
    outputs_tm = dict(h2i_tm.model.list_outputs(out_stream=None))

    lcoe_tm = outputs_tm["plant.finance_subgroup_renewables.electricity_finance_profast_model.LCOE"]

# Compare results
if run_dict.get("run_sequential", False) and run_dict.get("run_time_marching", False):
    inputs_pd_dict = percent_diff_dicts(inputs_seq, inputs_tm)
    outputs_pd_dict = percent_diff_dicts(outputs_seq, outputs_tm)

    in_abs, in_rel = find_nonzero_percent_diffs(inputs_pd_dict, dict(inputs_seq))
    out_abs, out_rel = find_nonzero_percent_diffs(outputs_pd_dict, dict(outputs_seq))

    pprint.pprint(in_abs)
    pprint.pprint(out_abs)
