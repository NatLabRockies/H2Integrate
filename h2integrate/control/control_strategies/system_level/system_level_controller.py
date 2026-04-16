"""
System-level dispatch controller.

A standalone ``om.ExplicitComponent`` that coordinates dispatch across
multiple technologies using simple heuristic logic to meet demand.

The controller:
  - Reads available production from fixed producers (e.g., wind)
  - Reads demand profiles and storage parameters from config
  - Outputs dispatch commands (set_points) to storage technologies

The grid fills any remaining gap through the existing ``technology_interconnections``
wiring (unmet demand flows to the grid naturally).

This controller is **not** tied to any specific technology's config and does
**not** use the Pyomo optimization framework.
"""

import numpy as np
import openmdao.api as om


class SystemLevelController(om.ExplicitComponent):
    """Heuristic dispatch controller for meeting demand across technologies.

    Reads wind (or other fixed producer) output, determines the gap between
    production and demand, and dispatches storage accordingly:

      1. If production > demand: charge storage with excess
      2. If production < demand: discharge storage to fill gap
      3. Any remaining gap is left for the grid (via existing wiring)

    The controller reads its topology and parameters from
    ``plant_config["system_level_control"]`` and storage parameters from
    ``technology_config``.
    """

    _time_step_bounds = (3600, 3600)

    def initialize(self):
        self.options.declare("plant_config", types=dict)
        self.options.declare("technology_config", types=dict)

    def setup(self):
        plant_config = self.options["plant_config"]
        technology_config = self.options["technology_config"]
        slc_config = plant_config["system_level_control"]

        self.n_timesteps = plant_config["plant"]["simulation"]["n_timesteps"]

        # Parse commodity stream topology
        self._fixed_producers = []  # [(tech, commodity)]
        self._storage_techs = []  # [(tech, commodity, params_dict)]
        self._demand_profiles = {}  # {commodity: demand_array}

        for stream_name, stream_cfg in slc_config["commodity_streams"].items():
            # Fixed producers: create an input for each
            for entry in stream_cfg.get("producers", []):
                if entry.get("role") == "fixed":
                    tech = entry["tech"]
                    self._fixed_producers.append((tech, stream_name))
                    self.add_input(
                        f"{tech}_{stream_name}_available",
                        shape=self.n_timesteps,
                        units=stream_cfg.get("units", None),
                        val=0.0,
                    )

            # Storage: create a dispatch output and read storage params from tech_config
            for entry in stream_cfg.get("storage", []):
                tech = entry["tech"]
                tech_cfg = technology_config["technologies"][tech]
                shared = tech_cfg.get("model_inputs", {}).get("shared_parameters", {})

                storage_params = {
                    "max_capacity": shared.get("max_capacity", 1e6),
                    "max_charge_rate": shared.get("max_charge_rate", 1e6),
                    "max_discharge_rate": shared.get("max_discharge_rate", 1e6),
                    "charge_efficiency": shared.get("charge_efficiency", 1.0),
                    "discharge_efficiency": shared.get("discharge_efficiency", 1.0),
                    "init_soc_fraction": shared.get("init_soc_fraction", 0.5),
                    "min_soc_fraction": shared.get("min_soc_fraction", 0.0),
                    "max_soc_fraction": shared.get("max_soc_fraction", 1.0),
                }

                self._storage_techs.append((tech, stream_name, storage_params))
                self.add_output(
                    f"{tech}_{stream_name}_dispatch",
                    shape=self.n_timesteps,
                    units=stream_cfg.get("units", None),
                    val=0.0,
                )

            # Demand: read profile from the demand tech's config
            for entry in stream_cfg.get("demands", []):
                tech = entry["tech"]
                tech_cfg = technology_config["technologies"][tech]
                perf_params = tech_cfg.get("model_inputs", {}).get("performance_parameters", {})
                demand_val = perf_params.get("demand_profile", 0.0)

                if isinstance(demand_val, int | float):
                    demand_val = np.full(self.n_timesteps, float(demand_val))
                else:
                    demand_val = np.array(demand_val, dtype=float)

                # Accumulate demand per commodity stream
                if stream_name in self._demand_profiles:
                    self._demand_profiles[stream_name] += demand_val
                else:
                    self._demand_profiles[stream_name] = demand_val.copy()

    def compute(self, inputs, outputs):
        """Run heuristic dispatch for each commodity stream."""
        for stream_name in {s for _, s in self._fixed_producers}:
            self._dispatch_stream(stream_name, inputs, outputs)

    def _dispatch_stream(self, stream_name, inputs, outputs):
        """Heuristic dispatch for a single commodity stream.

        Priority order:
          1. Use fixed production (wind, solar)
          2. Discharge storage to fill remaining demand
          3. Charge storage with excess production
          4. Any remaining gap is left for the grid
        """
        n = self.n_timesteps

        # Sum all fixed production for this stream
        total_fixed = np.zeros(n)
        for tech, sname in self._fixed_producers:
            if sname == stream_name:
                total_fixed += inputs[f"{tech}_{stream_name}_available"]

        # Get demand for this stream
        demand = self._demand_profiles.get(stream_name, np.zeros(n))

        # Dispatch each storage tech
        for tech, sname, params in self._storage_techs:
            if sname != stream_name:
                continue

            capacity = params["max_capacity"]
            max_charge = params["max_charge_rate"]
            max_discharge = params["max_discharge_rate"]
            charge_eff = params["charge_efficiency"]
            discharge_eff = params["discharge_efficiency"]
            min_soc = params["min_soc_fraction"] * capacity
            max_soc = params["max_soc_fraction"] * capacity

            soc = params["init_soc_fraction"] * capacity
            dispatch = np.zeros(n)

            for t in range(n):
                gap = demand[t] - total_fixed[t]

                if gap > 0:
                    # Need more — discharge battery
                    available_energy = (soc - min_soc) * discharge_eff
                    discharge = min(gap, max_discharge, max(0.0, available_energy))
                    dispatch[t] = discharge
                    soc -= discharge / discharge_eff
                else:
                    # Excess — charge battery
                    excess = -gap
                    room = (max_soc - soc) / charge_eff if charge_eff > 0 else 0.0
                    charge = min(excess, max_charge, max(0.0, room))
                    dispatch[t] = -charge
                    soc += charge * charge_eff

            outputs[f"{tech}_{stream_name}_dispatch"] = dispatch
