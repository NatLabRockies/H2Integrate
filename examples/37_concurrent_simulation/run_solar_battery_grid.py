import sys
import time
from copy import deepcopy
from pathlib import Path

import yaml
import numpy as np
import matplotlib.pyplot as plt

from h2integrate import H2IntegrateModel


sys.path.append(str(Path(__file__).resolve().parents[0]))
from CustomNLSolver import CustomNonLinearRunOnce


# Run one of both simulation paradigms by changing the flags in this dict
run_dict = {
    "run_sequential": True,
    "run_concurrent": True,
}


def load_yaml_to_dict(fpath):
    with Path(fpath).open() as f:
        config = yaml.safe_load(f)
    return config


# Load config files into dict
config_root = Path(__file__).parent
config_path = config_root / "solar_battery_grid.yaml"

# Load top level config
config = load_yaml_to_dict(config_path)

# Fill driver config
driver_config_path = config_root / config["driver_config"]
config["driver_config"] = load_yaml_to_dict(driver_config_path)

# Fill technology config
technology_config_path = config_root / config["technology_config"]
config["technology_config"] = load_yaml_to_dict(technology_config_path)

# Fill plant config
plant_config_path = config_root / config["plant_config"]
config["plant_config"] = load_yaml_to_dict(plant_config_path)


def get_io(name, io_list):
    # Get the value of a specific input or output from the H2I inputs and outputs
    return [io[1]["val"] for io in io_list if io[0] == name][0]


# Run simulation sequentially one subsystem at a time
if run_dict.get("run_sequential", False):
    config_seq = deepcopy(config)
    config_seq["plant_config"]["plant"]["simulation"]["n_timesteps"] = 8760
    config_seq["plant_config"]["plant"]["simulation"]["n_steps_per_compute"] = 8760

    # Create an H2I model for standard year-long simulation
    h2i_seq = H2IntegrateModel(config_seq)

    t0 = time.time()
    # Run the model
    h2i_seq.run()
    t1 = time.time()

    print(f"Sequential took {t1 - t0:.3f} seconds")

    # Post-process the results
    h2i_seq.post_process(print_results=False)

    inputs_seq = h2i_seq.model.list_inputs(out_stream=None)
    outputs_seq = h2i_seq.model.list_outputs(out_stream=None)

    lcoe_seq = get_io(
        "plant.finance_subgroup_renewables.electricity_finance_profast_model.LCOE",
        outputs_seq,
    )

# Run the simulation concurrently for all subsystems one step at a time
if run_dict.get("run_concurrent", False):
    config_con = deepcopy(config)

    config_con["plant_config"]["plant"]["simulation"]["n_timesteps"] = 8760
    config_con["plant_config"]["plant"]["simulation"]["n_steps_per_compute"] = 24

    # Create an H2I model for steppable simulation
    h2i_con = H2IntegrateModel(config_con)

    # Set plant group nonlinear solver to custom steppable solver
    h2i_con.prob.model.plant.nonlinear_solver = CustomNonLinearRunOnce()
    # h2i_con.prob.model.plant.linear_solver = CustomLinearRunOnce()

    t0 = time.time()
    # Run the model
    h2i_con.run()
    t1 = time.time()

    print(f"Concurrent took {t1 - t0:.3f} seconds")

    # Post-process the results
    h2i_con.post_process(print_results=False)

    inputs_con = h2i_con.model.list_inputs(out_stream=None)
    outputs_con = h2i_con.model.list_outputs(out_stream=None)

    lcoe_con = get_io(
        "plant.finance_subgroup_renewables.electricity_finance_profast_model.LCOE",
        outputs_con,
    )

# Compare results
if run_dict.get("run_sequential", False) and run_dict.get("run_concurrent", False):

    def percent_diff(v1, v2):
        # Calculate the percent difference between two numbers or arrays
        return np.nan_to_num((v2 - v1) / (0.5 * (v1 + v2)))

    def percent_diff_dicts(d1, d2):
        # Construct a dict of percent differences from two dicts with the same entries
        d1 = dict(d1)
        d2 = dict(d2)

        d_out = {}
        for k1, v1 in d1.items():
            assert k1 in d2.keys()
            v2 = d2[k1]

            if isinstance(v1["val"], dict):
                # If the H2I input or output is more complicated than an array, skip it
                continue

            pd = percent_diff(v1["val"], v2["val"])

            d_out.update({k1: np.linalg.norm(pd)})

        return d_out

    def find_nonzero_percent_diffs(pd_dict):
        # Return only the dict items that are non-zero
        return {k: v for k, v in pd_dict.items() if np.abs(v) > 1e-8}

    inputs_pd_dict = percent_diff_dicts(inputs_seq, inputs_con)
    outputs_pd_dict = percent_diff_dicts(outputs_seq, outputs_con)

    find_nonzero_percent_diffs(inputs_pd_dict)
    find_nonzero_percent_diffs(outputs_pd_dict)

    def plot_diff(key, io="outputs"):
        if io == "outputs":
            seq = dict(outputs_seq)
            con = dict(outputs_con)
        elif io == "inputs":
            seq = dict(inputs_seq)
            con = dict(inputs_con)

        fig, ax = plt.subplots(2, 1, sharex="all", sharey="all", layout="constrained")

        ax[0].plot(seq[key]["val"], label="sequential")
        ax[0].plot(con[key]["val"], label="concurrent")
        ax[0].legend()

        ax[1].axhline(0, color="black", linewidth=1)
        ax[1].fill_between(
            np.arange(0, len(seq[key]["val"]), 1),
            np.zeros_like(seq[key]["val"]),
            seq[key]["val"] - con[key]["val"],
        )

        ax[0].set_title(key)

    # plot_diff("plant.electrical_load_demand.GenericDemandComponent.electricity_out")
    # plot_diff('plant.grid_buy.GridPerformanceModel.electricity_out')
    # plot_diff('plant.battery.StoragePerformanceModel.SOC')
