import numpy as np
from matplotlib import pyplot as plt

from h2integrate.core.h2integrate_model import H2IntegrateModel


# Create an H2Integrate model
model = H2IntegrateModel("pyomo_heuristic_dispatch.yaml")

demand_profile = np.ones(8760) * 50.0


# TODO: Update with demand module once it is developed
model.setup()
model.prob.set_val("battery.electricity_demand", demand_profile, units="MW")

# Run the model
model.run()

# Plot the results
fig, ax = plt.subplots(2, 1, sharex=True)

start_hour = 0
end_hour = 200

ax[0].plot(
    range(start_hour, end_hour),
    model.prob.get_val("battery.SOC", units="percent")[start_hour:end_hour],
    label="SOC",
)
ax[0].set_ylabel("SOC (%)")
ax[0].set_ylim([0, 110])
ax[0].axhline(y=90.0, linestyle=":", color="k", alpha=0.5, label="Max Charge")
ax[0].legend()

ax[1].plot(
    range(start_hour, end_hour),
    model.prob.get_val("battery.electricity_in", units="MW")[start_hour:end_hour],
    linestyle="-",
    label="Electricity In (MW)",
)
ax[1].plot(
    range(start_hour, end_hour),
    model.prob.get_val("battery.unused_electricity_out", units="MW")[start_hour:end_hour],
    linestyle=":",
    label="Unused Electricity (MW)",
)
ax[1].plot(
    range(start_hour, end_hour),
    model.prob.get_val("battery.unmet_electricity_demand_out", units="MW")[start_hour:end_hour],
    linestyle=":",
    label="Unmet Electrical Demand (MW)",
)
ax[1].plot(
    range(start_hour, end_hour),
    model.prob.get_val("battery.electricity_out", units="MW")[start_hour:end_hour],
    linestyle="-",
    label="Electricity Out (MW)",
)
ax[1].plot(
    range(start_hour, end_hour),
    model.prob.get_val("battery.battery_electricity_discharge", units="MW")[start_hour:end_hour],
    linestyle="-.",
    label="Battery Electricity Out (MW)",
)
ax[1].plot(
    range(start_hour, end_hour),
    demand_profile[start_hour:end_hour],
    linestyle="--",
    label="Electrical Demand (MW)",
)
ax[1].set_ylim([-7e2, 7e2])
ax[1].set_ylabel("Electricity Hourly (MW)")
ax[1].set_xlabel("Timestep (hr)")

plt.legend(ncol=2, frameon=False)
plt.tight_layout()
plt.savefig("plot.png", dpi=300)
