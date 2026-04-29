import numpy as np
import openmdao.api as om


class SystemLevelControl(om.ExplicitComponent):
    """System-level control that satisfies demand across all technologies.

    Reads pre-computed technology classification from
    ``plant_config["system_level_control"]``, which must contain:

    - ``commodity``: the commodity being controlled (e.g. "electricity")
    - ``commodity_units``: units string (or None)
    - ``demand_tech``: name of the demand technology
    - ``curtailable_techs``: list of curtailable technology names
    - ``dispatchable_techs``: list of dispatchable technology names
    - ``storage_techs``: list of storage technology names

    Only one commodity demand stream is supported.  At each timestep,
    curtailable production is applied first, then the remaining demand
    is distributed equally across dispatchable technologies.
    """

    def initialize(self):
        self.options.declare("driver_config", types=dict)
        self.options.declare("plant_config", types=dict)
        self.options.declare("tech_config", types=dict)

    def setup(self):
        plant_config = self.options["plant_config"]
        slc_config = plant_config["system_level_control"]

        self.n_timesteps = plant_config["plant"]["simulation"]["n_timesteps"]

        # Read pre-computed classification from plant_config
        self.commodity = slc_config["commodity"]
        self.commodity_units = slc_config.get("commodity_units", None)
        self.demand_tech = slc_config["demand_tech"]
        self.curtailable_techs = list(slc_config.get("curtailable_techs", []))
        self.dispatchable_techs = list(slc_config.get("dispatchable_techs", []))
        self.storage_techs = list(slc_config.get("storage_techs", []))

        # Input: demand profile (default value from config)
        demand_profile = slc_config.get("demand_profile", 0.0)
        self.demand_input_name = f"{self.commodity}_demand"
        self.add_input(
            self.demand_input_name,
            val=demand_profile,
            shape=self.n_timesteps,
            units=self.commodity_units,
            desc=f"Demand profile of {self.commodity}",
        )

        # ---- Add OpenMDAO inputs / outputs per tech category ----
        # Curtailable techs: read output + rated production, write set_point
        self.curtailable_input_names = []
        self.curtailable_output_names = []
        self.curtailable_rated_names = []
        for tech_name in self.curtailable_techs:
            in_name = f"{tech_name}_{self.commodity}_out"
            out_name = f"{tech_name}_{self.commodity}_set_point"
            rated_name = f"{tech_name}_rated_{self.commodity}_production"
            self.add_input(
                in_name,
                val=0.0,
                shape=self.n_timesteps,
                units=self.commodity_units,
                desc=f"{self.commodity} output from {tech_name}",
            )
            self.add_input(
                rated_name,
                val=0.0,
                units=self.commodity_units,
                desc=f"Rated {self.commodity} production for {tech_name}",
            )
            self.add_output(
                out_name,
                val=0.0,
                shape=self.n_timesteps,
                units=self.commodity_units,
                desc=f"Set point for {tech_name} {self.commodity} curtailment",
            )
            self.curtailable_input_names.append(in_name)
            self.curtailable_output_names.append(out_name)
            self.curtailable_rated_names.append(rated_name)

        # Compute a reasonable initial set_point for dispatchable techs
        n_dispatchable = len(self.dispatchable_techs)
        if n_dispatchable > 0:
            if np.isscalar(demand_profile):
                initial_set_point = demand_profile / n_dispatchable
            else:
                initial_set_point = np.array(demand_profile) / n_dispatchable
        else:
            initial_set_point = 0.0

        self.dispatchable_input_names = []
        self.dispatchable_output_names = []
        self.dispatchable_rated_names = []
        for tech_name in self.dispatchable_techs:
            in_name = f"{tech_name}_{self.commodity}_out"
            out_name = f"{tech_name}_{self.commodity}_set_point"
            rated_name = f"{tech_name}_rated_{self.commodity}_production"
            self.add_input(
                in_name,
                val=0.0,
                shape=self.n_timesteps,
                units=self.commodity_units,
                desc=f"{self.commodity} output from {tech_name}",
            )
            self.add_input(
                rated_name,
                val=0.0,
                units=self.commodity_units,
                desc=f"Rated {self.commodity} production for {tech_name}",
            )
            self.add_output(
                out_name,
                val=initial_set_point,
                shape=self.n_timesteps,
                units=self.commodity_units,
                desc=f"Set point for {tech_name} {self.commodity} production",
            )
            self.dispatchable_input_names.append(in_name)
            self.dispatchable_output_names.append(out_name)
            self.dispatchable_rated_names.append(rated_name)

        self.storage_input_names = []
        self.storage_output_names = []
        for tech_name in self.storage_techs:
            in_name = f"{tech_name}_{self.commodity}_out"
            out_name = f"{tech_name}_{self.commodity}_set_point"
            self.add_input(
                in_name,
                val=0.0,
                shape=self.n_timesteps,
                units=self.commodity_units,
                desc=f"{self.commodity} output from {tech_name}",
            )
            self.add_output(
                out_name,
                val=0.0,
                shape=self.n_timesteps,
                units=self.commodity_units,
                desc=f"Set point for {tech_name} {self.commodity} production",
            )
            self.storage_input_names.append(in_name)
            self.storage_output_names.append(out_name)

    def compute(self, inputs, outputs):
        demand = inputs[self.demand_input_name].copy()

        # 1. Curtailable techs: set_point = rated production (no curtailment)
        for in_name, out_name, rated_name in zip(
            self.curtailable_input_names,
            self.curtailable_output_names,
            self.curtailable_rated_names,
        ):
            curtailable_output = inputs[in_name]
            outputs[out_name] = inputs[rated_name] * np.ones(self.n_timesteps)
            demand -= curtailable_output

        # Remaining demand after curtailable production
        remaining = np.maximum(demand, 0.0)

        # 2. Distribute remaining demand equally across dispatchable techs
        n_dispatchable = len(self.dispatchable_output_names)
        if n_dispatchable > 0:
            share = remaining / n_dispatchable
            for out_name in self.dispatchable_output_names:
                outputs[out_name] = share

        # 3. Storage techs get zero set_point for now
        for out_name in self.storage_output_names:
            outputs[out_name] = np.zeros(self.n_timesteps)
