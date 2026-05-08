import numpy as np
from matplotlib import pyplot as plt

from h2integrate import H2IntegrateModel


# Create an H2Integrate model
model = H2IntegrateModel("pyomo_optimized_dispatch.yaml")

# --- Parameters ---
amplitude = 0.9  # Amplitude of the sine wave
frequency = 0.05  # Frequency of the sine wave in Hz
duration = 8760.0  # Duration of the signal in seconds
sampling_rate = 1  # Number of samples per second (Fs)

# Noise parameters
noise_mean = 0.0
noise_std_dev = 0.1  # Standard deviation controls the noise intensity

# --- Generate the Time Vector ---
# Create a time array from 0 to duration with a specific sampling rate
t = np.linspace(1.0, duration, int(sampling_rate * duration), endpoint=True)

# --- Generate the Pure Sine Wave Signal ---
# Formula: y(t) = A * sin(2 * pi * f * t)
pure_signal = amplitude * np.sin(2.0 * np.pi * frequency * t)

# --- Generate the Random Gaussian Noise ---
# Create noise with the same shape as the time vector
rng = np.random.default_rng()
noise = rng.normal(loc=noise_mean, scale=noise_std_dev, size=t.shape)

# --- Create the Noisy Signal ---
noisy_signal = (pure_signal + noise) * 0.04 + 0.04 * np.ones(len(t))

commodity_met_value_profile = np.ones(8760) * 1
commodity_buy_price_profile = noisy_signal

demand_profile = np.ones(8760) * 100.0


# TODO: Update with demand module once it is developed
model.setup()
model.prob.set_val("battery.electricity_demand", demand_profile, units="MW")
# model.prob.set_val("battery.demand_met_value", commodity_met_value_profile, units="USD/kW")
model.prob.set_val("battery.electricity_buy_price", commodity_buy_price_profile, units="USD/kW")
# model.prob.set_val("grid_buy.electricity_buy_price", commodity_buy_price_profile, units="USD/kW")

# Run the model
model.run()

model.post_process()

# Plot the results
fig, ax = plt.subplots(3, 1, sharex=True, figsize=(8, 6))

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
    model.prob.get_val("battery.electricity_bought_for_storage", units="MW")[start_hour:end_hour],
    linestyle="-",
    label="Electricity Bought (MW)",
)
ax[1].plot(
    range(start_hour, end_hour),
    model.prob.get_val("battery.battery_electricity_out", units="MW")[start_hour:end_hour],
    linestyle="-.",
    label="Battery Electricity Out (MW)",
)

print(min(model.prob.get_val("battery.electricity_out", units="MW")))
print(min(model.prob.get_val("battery.battery_electricity_out", units="MW")))
ax[1].plot(
    range(start_hour, end_hour),
    demand_profile[start_hour:end_hour],
    linestyle="--",
    label="Electrical Demand (MW)",
)
ax[1].set_ylim([-1e2, 2.5e2])
ax[1].set_ylabel("Electricity Hourly (MW)")
ax[1].legend()

ax[2].plot(
    range(start_hour, end_hour),
    model.prob.get_val("battery.electricity_buy_price", units="USD/MW")[start_hour:end_hour],
    label="Grid Purchase Price ($/MW)",
)
ax[2].set_ylabel("Grid Purchase Price ($/MW)")
ax[2].set_xlabel("Timestep (hr)")

plt.legend(ncol=2, frameon=False)
plt.tight_layout()
plt.savefig("optimized_dispatch_plot.png", dpi=300)
