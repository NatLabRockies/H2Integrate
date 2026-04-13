import matplotlib.pyplot as plt

from h2integrate.core.h2integrate_model import H2IntegrateModel


h2i = H2IntegrateModel("wind_battery_dispatch.yaml")

# Run the model
h2i.run()

h2i.post_process()

# Battery dispatch plotting
model = h2i
fig, ax = plt.subplots(2, 1, sharex=True)

start_hour = 0
end_hour = 200
total_time_steps = model.prob.get_val("battery.electricity_soc", units="unitless").size
demand_profile = [
    model.technology_config["technologies"]["battery"]["model_inputs"]["control_parameters"][
        "demand_profile"
    ]
    * 1e-3
] * total_time_steps

ax[0].plot(
    range(start_hour, end_hour),
    model.prob.get_val("battery.electricity_soc", units="percent")[start_hour:end_hour],
    label="SOC",
    linewidth=2,
)
ax[0].set_ylabel("SOC (%)")
ax[0].set_ylim([0, 110])

ax[1].plot(
    range(start_hour, end_hour),
    model.prob.get_val("battery.electricity_in", units="MW")[start_hour:end_hour],
    linestyle="-",
    label="Electricity In (MW)",
    linewidth=2,
)
ax[1].plot(
    range(start_hour, end_hour),
    model.prob.get_val("battery.unused_electricity_out", units="MW")[start_hour:end_hour],
    linestyle=":",
    label="Unused Electricity commodity (MW)",
    linewidth=2,
)
ax[1].plot(
    range(start_hour, end_hour),
    model.prob.get_val("battery.unmet_electricity_demand_out", units="MW")[start_hour:end_hour],
    linestyle=":",
    label="Electricity Unmet Demand (MW)",
    linewidth=2,
)
ax[1].plot(
    range(start_hour, end_hour),
    model.prob.get_val("battery.electricity_out", units="MW")[start_hour:end_hour],
    linestyle="-",
    label="Electricity Out (MW)",
    linewidth=2,
)
ax[1].plot(
    range(start_hour, end_hour),
    demand_profile[start_hour:end_hour],
    linestyle="--",
    label="Electricity Demand (MW)",
    linewidth=2,
)
ax[1].set_ylabel("Electricity Hourly (MW)")
ax[1].set_xlabel("Timestep (hr)")

plt.legend(ncol=2, frameon=False)
plt.tight_layout()
plt.show()
