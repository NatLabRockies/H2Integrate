import numpy as np
import openmdao.api as om


class SystemLevelControl(om.ExplicitComponent):
    """System-level control that satisfies demand evenly across all technologies.

    Parses ``technology_interconnections`` and ``tech_config`` to identify:

    - **Demand technology**: the single component with a ``demand_profile``
    - **Dispatchable technologies**: all producing technologies found in
      4-element connections (excluding demand techs, combiners, splitters,
      and feedstocks)

    Only one commodity demand stream is supported.  At each timestep the
    demand is distributed equally as set-points to the dispatchable
    technologies.
    """

    def initialize(self):
        self.options.declare("driver_config", types=dict)
        self.options.declare("plant_config", types=dict)
        self.options.declare("tech_config", types=dict)

    def setup(self):
        plant_config = self.options["plant_config"]
        tech_config = self.options["tech_config"]

        self.n_timesteps = plant_config["plant"]["simulation"]["n_timesteps"]
        interconnections = plant_config.get("technology_interconnections", [])
        technologies = tech_config.get("technologies", {})

        # ---- 1. Identify the (single) demand technology from tech_config ----
        # A demand tech has ``demand_profile`` in its performance or shared params.
        self.commodity = None
        self.demand_profile = None
        self.commodity_units = None
        for tech_name, tech_def in technologies.items():
            model_inputs = tech_def.get("model_inputs", {})
            perf_params = model_inputs.get("performance_parameters", {})
            shared_params = model_inputs.get("shared_parameters", {})
            all_params = {**shared_params, **perf_params}

            if "demand_profile" in all_params:
                if self.commodity is not None:
                    raise ValueError(
                        "SystemLevelControl currently supports only one demand "
                        f"stream, but found demands for both '{self.commodity}' "
                        f"and '{all_params['commodity']}'."
                    )
                self.commodity = all_params["commodity"]
                self.commodity_units = all_params.get("commodity_rate_units", None)
                self.demand_profile = all_params["demand_profile"]
                self.demand_tech = tech_name

        # ---- 2. Identify all dispatchable (producing) technologies ----
        # Every source tech in a 4-element connection is dispatchable,
        # excluding demand techs, infrastructure (combiners, splitters),
        # and feedstocks.
        demand_tech_names = {self.demand_tech} if self.commodity else set()

        infrastructure_techs = set()
        feedstock_techs = set()
        for tech_name, tech_def in technologies.items():
            model_name = tech_def.get("performance_model", {}).get("model", "")
            if "Combiner" in model_name or "Splitter" in model_name:
                infrastructure_techs.add(tech_name)
            if "Feedstock" in model_name:
                feedstock_techs.add(tech_name)

        excluded = demand_tech_names | infrastructure_techs | feedstock_techs

        self.dispatchable_techs = []  # [tech_name, ...]
        seen = set()
        for connection in interconnections:
            if len(connection) == 4:
                source_tech, _dest, commodity, _transport = connection
                if (
                    commodity == self.commodity
                    and source_tech not in excluded
                    and source_tech not in seen
                ):
                    self.dispatchable_techs.append(source_tech)
                    seen.add(source_tech)

        # Also pick up destination techs from 3-element set-point connections
        # that weren't already found via 4-element connections.
        for connection in interconnections:
            if len(connection) == 3:
                _source, dest_tech, var_mapping = connection
                if isinstance(var_mapping, list | tuple) and len(var_mapping) == 2:
                    _src_var, dst_var = var_mapping
                    if "_set_point" in dst_var:
                        commodity = dst_var.replace("_set_point", "")
                        if (
                            commodity == self.commodity
                            and dest_tech not in excluded
                            and dest_tech not in seen
                        ):
                            self.dispatchable_techs.append(dest_tech)
                            seen.add(dest_tech)

        # ---- 3. Add OpenMDAO inputs / outputs ----
        # Input: demand profile
        self.demand_input_name = f"{self.commodity}_demand"
        self.add_input(
            self.demand_input_name,
            val=self.demand_profile,
            shape=self.n_timesteps,
            units=self.commodity_units,
            desc=f"Demand profile of {self.commodity}",
        )

        # Inputs: commodity output from each dispatchable tech
        self.commodity_input_names = []
        for tech_name in self.dispatchable_techs:
            var_name = f"{tech_name}_{self.commodity}_out"
            self.add_input(
                var_name,
                val=0.0,
                shape=self.n_timesteps,
                units=self.commodity_units,
                desc=f"{self.commodity} output from {tech_name}",
            )
            self.commodity_input_names.append(var_name)

        # Outputs: set-points for all dispatchable techs
        self.set_point_output_names = []
        for tech_name in self.dispatchable_techs:
            var_name = f"{tech_name}_{self.commodity}_set_point"
            self.add_output(
                var_name,
                val=0.0,
                shape=self.n_timesteps,
                units=self.commodity_units,
                desc=f"Set point for {tech_name} {self.commodity} production",
            )
            self.set_point_output_names.append(var_name)

    def compute(self, inputs, outputs):
        demand = np.maximum(inputs[self.demand_input_name], 0.0)

        # Sum actual commodity output from all dispatchable techs
        total_supply = np.zeros(self.n_timesteps)
        for var_name in self.commodity_input_names:
            total_supply += inputs[var_name]

        # Gap between demand and current total supply
        gap = demand - total_supply

        # Adjust each tech's set_point: current output + its share of the gap
        n_dispatchable = len(self.set_point_output_names)
        if n_dispatchable > 0:
            correction = gap / n_dispatchable
            for var_name, in_name in zip(self.set_point_output_names, self.commodity_input_names):
                outputs[var_name] = inputs[in_name] + correction
