from h2integrate.core.h2integrate_model import H2IntegrateModel


##################################
# Create an H2I model with a fixed electricity load demand
h2i = H2IntegrateModel("solar_wind_ng_demand.yaml")

# Run the model
h2i.run()

# Post-process the results
h2i.post_process()


##################################
# Create H2I model but replace electrical load demand to be flexible
h2i_flexible = H2IntegrateModel("solar_wind_ng_flexible_demand.yaml")

# Run the model
h2i_flexible.run()

# Post-process the results
h2i_flexible.post_process()

import matplotlib.pyplot as plt


# Battery dispatch plotting
model = h2i_flexible
fig, ax = plt.subplots(2, 1, sharex=True, figsize=(11, 9))

start_hour = 0
end_hour = 200
total_time_steps = model.prob.get_val("wind.electricity_out").size
demand_profile = [
    model.technology_config["technologies"]["electrical_load_demand"]["model_inputs"][
        "control_parameters"
    ]["demand_profile"]
    * 1e-3
] * total_time_steps

# First subplot for wind and solar production and baseline demand profile
ax[0].plot(
    range(start_hour, end_hour),
    model.prob.get_val("wind.electricity_out", units="MW")[start_hour:end_hour],
    linestyle="-",
    label="Wind Electricity (MW)",
    linewidth=2,
    color="blue",
)
ax[0].plot(
    range(start_hour, end_hour),
    model.prob.get_val("solar.electricity_out", units="MW")[start_hour:end_hour],
    linestyle="-",
    label="Solar Electricity (MW)",
    linewidth=2,
    color="gold",
)

ax[0].plot(
    range(start_hour, end_hour),
    demand_profile[start_hour:end_hour],
    linestyle="--",
    label="Baseline Electricity Demand (MW)",
    linewidth=2,
)
ax[0].set_ylabel("Generation (MW)")
ax[0].legend(loc="upper right")

# Second subplot for renewables electricity, NG electricity, and flexible demand profile
ax[1].plot(
    range(start_hour, end_hour),
    model.prob.get_val("combiner.electricity_out", units="MW")[start_hour:end_hour],
    linestyle="-",
    label="Combined Wind+Solar Electricity (MW)",
    linewidth=2,
    color="green",
)
ax[1].plot(
    range(start_hour, end_hour),
    model.prob.get_val("natural_gas_plant.electricity_out", units="MW")[start_hour:end_hour],
    linestyle="-",
    label="NG Plant Electricity (MW)",
    linewidth=2,
    color="orange",
)
ax[1].plot(
    range(start_hour, end_hour),
    model.prob.get_val("electrical_load_demand.electricity_flexible_demand_profile", units="MW")[
        start_hour:end_hour
    ],
    linestyle="--",
    label="Flexible Demand Profile (MW)",
    linewidth=2,
    color="purple",
)
ax[1].set_ylabel("Generation & Demand (MW)")
ax[1].set_xlabel("Timestep (hr)")
ax[1].legend(loc="upper right")

plt.tight_layout()
plt.show()
