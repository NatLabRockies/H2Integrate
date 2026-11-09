import time
import pprint
from copy import deepcopy
from pathlib import Path

import yaml

from h2integrate import H2IntegrateModel, load_tech_yaml, load_plant_yaml, load_driver_yaml
from h2integrate.core.dict_utils import percent_diff_dicts, find_nonzero_percent_diffs


# Run one of both simulation paradigms by changing the flags in this dict
run_dict = {
    "run_sequential": True,
    "run_time_marching": True,
}

# Load config files into dict
config_root = Path(__file__).parent
config_path = config_root / "config.yaml"

# Load top level config
with Path(config_path).open() as f:
    config = yaml.safe_load(f)

config["driver_config"] = load_driver_yaml(config_root / config["driver_config"])
config["technology_config"] = load_tech_yaml(config_root / config["technology_config"])
config["plant_config"] = load_plant_yaml(config_root / config["plant_config"])

# Set up config dicts for all three rule-based system level controllers
SLC_base_config = {
    "control_strategy": "DemandFollowingControl",
    "demand_component": "electrical_load_demand",
    "solver_options": {
        "solver_name": "gauss_seidel",
        "max_iter": 20,
        "convergence_tolerance": 1.0e-6,
    },
}

# Cost minimiztion control
cost_minimization_config = deepcopy(SLC_base_config)
cost_minimization_config["control_strategy"] = "CostMinimizationControl"

# Demand following control
demand_following_config = deepcopy(SLC_base_config)
demand_following_config["control_strategy"] = "DemandFollowingControl"

# Profit maximization control
profit_maximization_config = deepcopy(SLC_base_config)
profit_maximization_config["control_strategy"] = "ProfitMaximizationControl"
profit_maximization_config["control_parameters"] = {
    "commodity_sell_price": 0.06,  # $/kWh default; overridden in run script
    "cost_per_tech": {
        "natural_gas_plant": "feedstock",  # use upstream feedstock (ng_feedstock) VarOpEx
        "grid_buy": "buy_price",  # use electricity_buy_price from cost config
    },
}

SLC_configs = {
    "demand_following": demand_following_config,
    "cost_minimization": cost_minimization_config,
    "profit_maximization": profit_maximization_config,
}

# Loop over the three rule-based SLC options and simulate sequential and time-marching h2i run.
for k, v in SLC_configs.items():
    print(f"System level controller: {k}")
    config["plant_config"]["system_level_control"] = v

    # Run simulation sequentially one subsystem at a time
    if run_dict.get("run_sequential", False):
        config_seq = deepcopy(config)
        config_seq["plant_config"]["plant"]["simulation"]["n_timesteps"] = 8760
        config_seq["plant_config"]["plant"]["simulation"]["n_timesteps_window"] = 8760

        # Create an H2I model for standard year-long simulation
        h2i_seq = H2IntegrateModel(config_seq)

        t0 = time.time()
        # Run the model
        h2i_seq.run()
        t1 = time.time()

        print(f"Sequential took {t1 - t0:.3f} seconds")

        inputs_seq = dict(h2i_seq.model.list_inputs(out_stream=None))
        outputs_seq = dict(h2i_seq.model.list_outputs(out_stream=None))

    # Run the simulation concurrently for all subsystems one step at a time
    if run_dict.get("run_time_marching", False):
        config_con = deepcopy(config)

        config_con["plant_config"]["plant"]["simulation"]["n_timesteps"] = 8760
        config_con["plant_config"]["plant"]["simulation"]["n_timesteps_window"] = 12

        # Create an H2I model for steppable simulation
        h2i_con = H2IntegrateModel(config_con)

        t0 = time.time()
        # Run the model
        h2i_con.run()
        t1 = time.time()

        print(f"Time marching took {t1 - t0:.3f} seconds")

        inputs_con = dict(h2i_con.model.list_inputs(out_stream=None))
        outputs_con = dict(h2i_con.model.list_outputs(out_stream=None))

    # Compare results
    if run_dict.get("run_sequential", False) and run_dict.get("run_time_marching", False):
        inputs_pd_dict = percent_diff_dicts(inputs_seq, inputs_con)
        outputs_pd_dict = percent_diff_dicts(outputs_seq, outputs_con)

        in_abs, in_rel = find_nonzero_percent_diffs(inputs_pd_dict, dict(inputs_seq))
        out_abs, out_rel = find_nonzero_percent_diffs(outputs_pd_dict, dict(outputs_seq))

        pprint.pprint(in_abs)
        pprint.pprint(out_abs)
