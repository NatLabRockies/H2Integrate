import time
from copy import deepcopy
from pathlib import Path

import yaml

from h2integrate import H2IntegrateModel, load_tech_yaml, load_plant_yaml, load_driver_yaml
from h2integrate.core.dict_utils import percent_diff_dicts, find_nonzero_percent_diffs


# Run one of both simulation paradigms by changing the flags in this dict
run_dict = {
    "run_sequential": True,
    "run_concurrent": True,
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
    config_seq["plant_config"]["plant"]["simulation"]["n_timesteps"] = 8760
    config_seq["plant_config"]["plant"]["simulation"]["n_steps_per_compute"] = 8760
    # config_seq["plant_config"]["plant"]["simulation"].pop("n_steps_per_compute")

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


# Run the simulation concurrently for all subsystems one step at a time
if run_dict.get("run_concurrent", False):
    config_con = deepcopy(config)

    config_con["plant_config"]["plant"]["simulation"]["n_timesteps"] = 8760
    config_con["plant_config"]["plant"]["simulation"]["n_steps_per_compute"] = 24

    # Create an H2I model for steppable simulation
    h2i_con = H2IntegrateModel(config_con)

    t0 = time.time()
    # Run the model
    h2i_con.run()
    t1 = time.time()

    print(f"Concurrent took {t1 - t0:.3f} seconds")

    # Post-process the results
    h2i_con.post_process(print_results=False)

    inputs_con = dict(h2i_con.model.list_inputs(out_stream=None))
    outputs_con = dict(h2i_con.model.list_outputs(out_stream=None))

    lcoe_con = outputs_con[
        "plant.finance_subgroup_renewables.electricity_finance_profast_model.LCOE"
    ]

# Compare results
if run_dict.get("run_sequential", False) and run_dict.get("run_concurrent", False):
    inputs_pd_dict = percent_diff_dicts(inputs_seq, inputs_con)
    outputs_pd_dict = percent_diff_dicts(outputs_seq, outputs_con)

    in_abs, in_rel = find_nonzero_percent_diffs(inputs_pd_dict, dict(inputs_seq))
    out_abs, out_rel = find_nonzero_percent_diffs(outputs_pd_dict, dict(outputs_seq))

    print(in_abs)
    print(out_abs)
