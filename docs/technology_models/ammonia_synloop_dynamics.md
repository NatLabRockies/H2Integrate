---
jupytext:
  text_representation:
    extension: .md
    format_name: myst
    format_version: 0.13
    jupytext_version: 1.18.1
kernelspec:
  display_name: h2i-fork
  language: python
  name: python3
---

# Ammonia synloop dynamic operating constraints

The `AmmoniaSynLoopPerformanceModel` can be configured to enforce dynamic operating
constraints that approximate the response of a real Haber-Bosch synthesis loop to a
time-varying electricity supply. Three classes of constraint are available and can be
enabled independently or together:

- **Turndown**: a non-zero minimum production floor (as a fraction of rated capacity)
  while the plant remains "on".
- **Ramping**: upper bounds on how quickly production can increase or decrease between
  consecutive timesteps, expressed as a fraction of rated capacity per hour.
- **Start-up delays**: production losses applied to the first timesteps after the
  plant comes back online following a long enough off-period. Both warm- and cold-start
  events are supported, with independent off-time triggers and delay durations.

This page walks through each constraint by reusing the synloop fixtures from the
test suite, plotting the production response for an off-on cycle.

## Configuration parameters

The following keys are added to the `performance_parameters` block of an ammonia tech
config to enable dynamic behavior:

| Parameter | Units | Description |
| --- | --- | --- |
| `turndown_ratio` | fraction in [0, 1] | Minimum production while the plant is "on", as a fraction of rated capacity. |
| `ramp_up_rate_fraction` | fraction in [0, 1] | Maximum hourly ramp-up rate, as a fraction of rated capacity per hour. |
| `ramp_down_rate_fraction` | fraction in [0, 1] | Maximum hourly ramp-down rate, as a fraction of rated capacity per hour. |
| `include_cold_start` | bool | Enable cold-start delay losses. |
| `off_hours_cold_start` | hours | Minimum continuous off-time that triggers a cold-start delay. |
| `cold_start_delay_hours` | hours | Duration of zero production immediately after a cold start. |
| `include_warm_start` | bool | Enable warm-start delay losses. |
| `off_hours_warm_start` | hours | Minimum continuous off-time that triggers a warm-start delay. |
| `warm_start_delay_hours` | hours | Duration of zero (or partial) production after a warm start. |

If both warm and cold start are enabled and the same off-period is long enough to
trigger both, their multipliers are derived from the *same* pre-startup reference
profile and combined via element-wise multiplication. This means the order in which
the two passes are evaluated has no effect on the result, and a long cold-start delay
will not "fake" a second off-event that triggers an additional warm-start delay
further downstream.

## Worked example

The following snippet builds a small `AmmoniaSynLoopPerformanceModel` with one
synthetic off/on input profile and shows how each constraint changes the production
response. The model parameters mirror the unit-test fixtures in
`h2integrate/converters/ammonia/test/test_ammonia_synloop_dynamics.py`.

```{code-cell} ipython3
import copy
import numpy as np
import matplotlib.pyplot as plt
import openmdao.api as om

from h2integrate.converters.ammonia.ammonia_synloop import AmmoniaSynLoopPerformanceModel

n_timesteps = 30
dt = 3600  # seconds (1 hour)

plant_config = {
    "plant": {
        "plant_life": 30,
        "simulation": {"dt": dt, "n_timesteps": n_timesteps},
    },
}

base_synloop_config = {
    "model_inputs": {
        "shared_parameters": {
            "production_capacity": 50.0,
            "catalyst_consumption_rate": 0.000091295354067341,
            "catalyst_replacement_interval": 3,
        },
        "performance_parameters": {
            "size_mode": "normal",
            "capacity_factor": 0.9,
            "energy_demand": 1.0,
            "heat_output": 0.8299956,
            "feed_gas_t": 25.8,
            "feed_gas_p": 20,
            "feed_gas_x_n2": 0.25,
            "feed_gas_x_h2": 0.75,
            "feed_gas_mass_ratio": 1.13,
            "purge_gas_t": 7.5,
            "purge_gas_p": 275,
            "purge_gas_x_n2": 0.26,
            "purge_gas_x_h2": 0.68,
            "purge_gas_x_ar": 0.02,
            "purge_gas_x_nh3": 0.04,
            "purge_gas_mass_ratio": 0.07,
        },
    }
}

rated_capacity = base_synloop_config["model_inputs"]["shared_parameters"][
    "production_capacity"
]
energy_demand = base_synloop_config["model_inputs"]["performance_parameters"][
    "energy_demand"
]

# Build a richer demand profile that exercises every dynamic constraint:
#   - several on/off transitions (some long, some short)
#   - a sustained mid-level demand region (visible to turndown)
#   - sharp step changes (visible to ramping)
demand_profile = np.full(n_timesteps, rated_capacity)
demand_profile[3:7] = 0.0                    # 4-hr off block (triggers cold start)
demand_profile[10:11] = 0.0                  # 1-hr off (sub-threshold for cold)
demand_profile[14:16] = 0.3 * rated_capacity  # 2-hr below-turndown demand
demand_profile[19:23] = 0.0                  # 4-hr off block (triggers cold start again)
demand_profile[26:27] = 0.0                  # brief 1-hr dip
elec_in = demand_profile * energy_demand
cap_mult = 10.0e3
n2 = np.full(n_timesteps, 5.0 * cap_mult)
h2 = np.full(n_timesteps, 2.0 * cap_mult)


def run_with(dynamics):
    cfg = copy.deepcopy(base_synloop_config)
    cfg["model_inputs"]["performance_parameters"].update(dynamics)
    prob = om.Problem()
    comp = AmmoniaSynLoopPerformanceModel(
        plant_config=plant_config, tech_config=cfg, driver_config={}
    )
    prob.model.add_subsystem("comp", comp, promotes=["*"])
    prob.setup()
    prob.set_val("comp.hydrogen_in", h2, units="kg/h")
    prob.set_val("comp.nitrogen_in", n2, units="kg/h")
    prob.set_val("comp.electricity_in", elec_in, units="kW")
    prob.run_model()
    return prob.get_val("comp.ammonia_out", units="kg/h")


baseline = run_with({})
ramping = run_with({
    "turndown_ratio": 0.2,
    "ramp_up_rate_fraction": 0.4,
    "ramp_down_rate_fraction": 0.4,
})
cold_only = run_with({
    "turndown_ratio": 0.2,
    "include_cold_start": True,
    "off_hours_cold_start": 4,
    "cold_start_delay_hours": 2,
})
warm_cold = run_with({
    "turndown_ratio": 0.2,
    "include_cold_start": True,
    "off_hours_cold_start": 4,
    "cold_start_delay_hours": 2,
    "include_warm_start": True,
    "off_hours_warm_start": 0.5,
    "warm_start_delay_hours": 0.5,
})
```

```{code-cell} ipython3
hours = np.arange(n_timesteps)
fig, axes = plt.subplots(3, 1, figsize=(8, 8), sharex=True, dpi=150)

cases = [
    (axes[0], ramping, "C0", "s", "Ramping 40%/hr (with 20% turndown floor)"),
    (axes[1], cold_only, "C1", "^", "Cold start (with 20% turndown)"),
    (axes[2], warm_cold, "C3", "D", "Warm + cold start (with 20% turndown)"),
]
for ax, profile, color, marker, label in cases:
    ax.plot(hours, baseline, "-o", color="0.6", label="No dynamics", markersize=4)
    ax.plot(hours, profile, linestyle="--", marker=marker, color=color, label=label,
            markersize=4)
    ax.set_ylabel("NH$_3$ [kg/h]")
    ax.legend(loc="best", fontsize=9)
    ax.grid(True, alpha=0.3)

axes[0].set_title("Effect of dynamic operating constraints on ammonia production")
axes[-1].set_xlabel("Hour")
plt.tight_layout()
plt.show()
```

The baseline (gray) curve follows the electricity-limited demand directly. Each
panel overlays one dynamic constraint:

- **Ramping** caps the per-hour change in production, so transitions across the
  20% turndown floor and step changes in demand are spread over multiple hours.
  When ramping down, output is held at the turndown floor rather than going below it.
- **Cold start** introduces a 2-hour delay after every off-block longer than 4
  hours: the first two "on" hours after the long off-period are zeroed before full
  production resumes.
- **Warm + cold start** combines the cold-start behavior with an additional warm-
  start partial-loss applied to short off-periods (here, 0.5 hr off triggers a 0.5
  hr warm-start delay), visible as a partial dip on the very first on-hour after
  each short off-block.

## Example configuration

See `examples/12_ammonia_synloop/tech_config.yaml` for a complete YAML example with
all dynamic operating parameters enabled.
