from pathlib import Path

import matplotlib.pyplot as plt

import h2integrate
from h2integrate.core.file_utils import load_yaml


# This example runs a simulation of a simple-cycle natural gas plant with one
# 239 MW turbine that tries to serve a flat 200 MW load at the NLR Flatirons
# Campus in Boulder, CO, where thermodynamic effects mean the performance of the
# natural gas plant can vary significantly with ambient conditions.
#
# The example connects demand to the natural gas plant, and then the results are
# piped through the statistical components to analyze the demand satisfaction as
# well as summary statistics of the headroom of the natural gas plant.
#
# Overall, this demonstrates that 239 MW of natural gas capacity may not always
# be sufficient to meet a flat 200 MW load due to ambient condition variability.
# The statistical analysis components help quantify this variability and provide
# insights into the reliability of the natural gas plant under different ambient
# conditions.

# configuration
do_plots = False  # flip to True to show the plots

# import the configuration files and create an H2Integrate model
driver_config = load_yaml(Path("driver_config.yaml"))
tech_config = load_yaml(Path("tech_config.yaml"))
plant_config = load_yaml(Path("plant_config.yaml"))
h2i = h2integrate.H2IntegrateModel(
    {
        "name": "38_natural_gas_statistical",
        "driver_config": driver_config,
        "technology_config": tech_config,
        "plant_config": plant_config,
    }
)

# these are needed to ensure functional input-input connections
h2i.model.connect(
    "electrical_load_demand.electricity_demand",
    "output_stats.electricity_threshold",
)
h2i.model.set_input_defaults(
    "electrical_load_demand.electricity_demand",
    val=[
        tech_config["technologies"]["electrical_load_demand"]["model_inputs"][
            "performance_parameters"
        ]["demand_profile"]
        for _ in range(plant_config["plant"]["simulation"]["n_timesteps"])
    ],
    units=tech_config["technologies"]["electrical_load_demand"]["model_inputs"][
        "performance_parameters"
    ]["commodity_rate_units"],
)

# run the model
h2i.run()

# print the electricity surplus and deficit statistics
print("OUTPUT STATISTICS")
print(
    f"\tNET SURPLUS: "
    f"{h2i.model.get_val('output_stats.net_electricity_surplus', units='MW*h')[0]:.2f} MWh"
)
print(
    f"\tNET DEFICIT: "
    f"{h2i.model.get_val('output_stats.net_electricity_deficit', units='MW*h')[0]:.2f} MWh"
)
print(
    f"\tHOURS IN SURPLUS: "
    f"{h2i.model.get_val('output_stats.ratio_timestep_electricity_surplus')[0] * 100.0:.2f}%"
)
print(
    f"\tHOURS IN DEFICIT: "
    f"{h2i.model.get_val('output_stats.ratio_timestep_electricity_deficit')[0] * 100.0:.2f}%"
)

# print the headroom statistics
print("HEADROOM STATISTICS:")
print(f"\tMIN: {h2i.model.get_val('headroom_stats.electricity_min', units='MW')[0]:.2f} MW")
print(f"\tMEDIAN: {h2i.model.get_val('headroom_stats.electricity_median', units='MW')[0]:.2f} MW")
print(f"\tMEAN: {h2i.model.get_val('headroom_stats.electricity_mean', units='MW')[0]:.2f} MW")
print(f"\tMAX: {h2i.model.get_val('headroom_stats.electricity_max', units='MW')[0]:.2f} MW")
for pct, val in zip(
    h2i.model.plant.headroom_stats.SummaryStatisticsPerformanceModel.config.percentiles,
    h2i.model.get_val("headroom_stats.electricity_percentiles", units="MW"),
):
    print(f"\tPERCENTILE {pct:<6.3f}: {val:.2f} MW")

if do_plots:

    def compute_density_ideal(temperature, pressure):
        R = 8.314  # Universal gas constant in J/(mol*K)
        M = 0.02897  # Molar mass of air in kg/mol
        density = (pressure * M) / (R * (temperature + 273.15))
        return density

    # plot the electricity output of the natural gas plant...
    fig, ax = plt.subplots()
    ax.plot(h2i.model.get_val("natural_gas_plant.electricity_out"))
    ax.set_xlabel("hour index of year, $h$ (hours)")
    ax.set_ylabel("NGCT power output, $P_{\\mathrm{NG}}$ (MW)")
    plt.show()

    # plot the density, natural gas consumption, and electricity output of the NG plant
    fig, axes = plt.subplots(3, 1, sharex=True)
    axes[0].plot(
        compute_density_ideal(
            h2i.model.get_val("natural_gas_plant.solar_resource_data")["temperature"],
            h2i.model.get_val("natural_gas_plant.solar_resource_data")["pressure"] * 100,
        ),
        label="density",
    )

    axes[1].plot(
        h2i.model.get_val("natural_gas_plant.natural_gas_consumed", units="MMBtu/h"), label="NG"
    )

    axes[2].plot(h2i.model.get_val("natural_gas_plant.electricity_out"))

    axes[0].set_ylabel("density, \n $\\rho$ (kg/m$^3$)")
    axes[1].set_ylabel("NG consumption, \n $Q_{\\mathrm{NG}}$ (MMBtu/h)")
    axes[2].set_ylabel("NGCT power \n output, $P_{\\mathrm{NG}}$ (MW)")
    axes[-1].set_xlabel("hour index of year, $h$ (hours)")
    plt.show()
