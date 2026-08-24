from copy import deepcopy
from pathlib import Path

import yaml
import numpy as np
import matplotlib.pyplot as plt

from h2integrate import H2IntegrateModel


# Run one of both simulation paradigms by changing the flags in this dict
run_dict = {"run_sequential": True, "run_concurrent": True}


# Set up
def load_yaml_to_dict(fpath):
    with Path(fpath).open() as f:
        config = yaml.safe_load(f)
    return config


# Load config files into dict
config_root = Path(__file__).parent
config_path = config_root / "solar_battery_grid.yaml"

config = load_yaml_to_dict(config_path)

driver_config_path = config_root / config["driver_config"]
config["driver_config"] = load_yaml_to_dict(driver_config_path)

technology_config_path = config_root / config["technology_config"]
config["technology_config"] = load_yaml_to_dict(technology_config_path)


plant_config_path = config_root / config["plant_config"]
config["plant_config"] = load_yaml_to_dict(plant_config_path)


if run_dict.get("run_sequential", False):
    config_seq = deepcopy(config)
    config_seq["plant_config"]["plant"]["simulation"]["n_timesteps"] = 8760
    config_seq["plant_config"]["plant"]["simulation"]["n_steps_per_compute"] = 8760

    # Create an H2I model for standard year-long
    h2i_seq = H2IntegrateModel(config_seq)

    # Run the model
    h2i_seq.run()

    # Post-process the results
    h2i_seq.post_process()

    inputs_seq = h2i_seq.model.list_inputs()
    outputs_seq = h2i_seq.model.list_outputs()


if run_dict.get("run_concurrent", False):
    config_con = deepcopy(config)

    config_con["plant_config"]["plant"]["simulation"]["n_timesteps"] = 8760
    config_con["plant_config"]["plant"]["simulation"]["n_steps_per_compute"] = 24

    # Create an H2I model for steppable simulation
    h2i_con = H2IntegrateModel(config_con)

    # Run the model
    h2i_con.run()

    # Post-process the results
    h2i_con.post_process()

    inputs_con = h2i_con.model.list_inputs()
    outputs_con = h2i_con.model.list_outputs()


def get_io(name, io_list):
    return [io[1]["val"] for io in io_list if io[0] == name][0]


def fb_zero(ax, signal):
    t = np.arange(0, len(signal), 1)
    ax.fill_between(t, np.zeros_like(signal), signal)


if run_dict.get("run_sequential", False):
    fig, ax = plt.subplots(3, 1, sharex="all", layout="constrained")

    fb_zero(
        ax[0], get_io("plant.solar.PYSAMSolarPlantPerformanceModel.electricity_out", outputs_seq)
    )
    fb_zero(ax[0], get_io("plant.grid_buy.GridPerformanceModel.electricity_out", outputs_seq))
    fb_zero(ax[1], get_io("plant.battery.StoragePerformanceModel.electricity_out", outputs_seq))

    fig.suptitle("Sequential simulation")

if run_dict.get("run_concurrent", False):
    fig, ax = plt.subplots(3, 1, sharex="all", layout="constrained")

    fb_zero(
        ax[0], get_io("plant.solar.PYSAMSolarPlantPerformanceModel.electricity_out", outputs_con)
    )
    fb_zero(ax[0], get_io("plant.grid_buy.GridPerformanceModel.electricity_out", outputs_con))
    fb_zero(ax[1], get_io("plant.battery.StoragePerformanceModel.electricity_out", outputs_con))

    fig.suptitle("Concurrent simulation")

plt.show()

first_100 = np.array(
    [
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        -19348.82977025,
        17415.21948661,
        -21027.16348395,
        3245.96306701,
        -784.51058172,
        8585.02412613,
        9081.50327228,
        2832.79388389,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        -2854.30407163,
        2854.30407163,
        -13437.8609348,
        -18550.1990819,
        -21016.43956393,
        -3507.0785144,
        25000.0,
        25000.0,
        6511.57809503,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        -5651.75197964,
        5651.75197964,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
    ]
)
