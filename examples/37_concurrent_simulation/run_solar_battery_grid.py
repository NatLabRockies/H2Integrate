import numpy as np
import matplotlib.pyplot as plt

from h2integrate import H2IntegrateModel


# Create an H2I model
h2i = H2IntegrateModel("solar_battery_grid.yaml")

# Run the model
h2i.run()

# Post-process the results
h2i.post_process()


inputs = h2i.model.list_inputs()
outputs = h2i.model.list_outputs()


def get_io(name, io_list):
    return [io[1]["val"] for io in io_list if io[0] == name][0]


def fb_zero(ax, signal):
    t = np.arange(0, len(signal), 1)
    ax.fill_between(t, np.zeros_like(signal), signal)


fig, ax = plt.subplots(3, 1, sharex="all", layout="constrained")

fb_zero(ax[0], get_io("plant.solar.PYSAMSolarPlantPerformanceModel.electricity_out", outputs))
fb_zero(ax[0], get_io("plant.grid_buy.GridPerformanceModel.electricity_out", outputs))
fb_zero(ax[1], get_io("plant.battery.StoragePerformanceModel.electricity_out", outputs))


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
