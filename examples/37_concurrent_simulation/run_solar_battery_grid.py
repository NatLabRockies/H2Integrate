import time
from copy import deepcopy
from pathlib import Path

import yaml
import numpy as np
import matplotlib.pyplot as plt

from h2integrate import H2IntegrateModel, load_tech_yaml, load_plant_yaml, load_driver_yaml
from h2integrate.core.dict_utils import percent_diff_dicts, find_nonzero_percent_diffs
from h2integrate.core.concurrent_nl_solver import CustomNonLinearRunOnce


# sys.path.append(str(Path(__file__).resolve().parents[0]))
# from CustomNLSolver import CustomNonLinearRunOnce

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

    # Set plant group nonlinear solver to custom steppable solver
    h2i_con.prob.model.plant.nonlinear_solver = CustomNonLinearRunOnce(
        plant_config=h2i_con.plant_config
    )
    # h2i_con.prob.model.plant.linear_solver = CustomLinearRunOnce()

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

    plot_diff("plant.battery.StoragePerformanceModel.electricity_out")

    # plot_diff("plant.electrical_load_demand.GenericDemandComponent.electricity_out")
    plot_diff("plant.grid_buy.GridPerformanceModel.electricity_out")
    # plot_diff('plant.battery.StoragePerformanceModel.SOC')

    plot_diff("plant.battery.DemandOpenLoopStorageController.electricity_command_value")

    plt.show()
