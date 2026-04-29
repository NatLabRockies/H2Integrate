import numpy as np
import openmdao.api as om

from h2integrate.core.supported_models import supported_models


class SystemLevelControl(om.ExplicitComponent):
    """System-level control that satisfies demand across all technologies.

    Parses ``tech_config`` to classify each technology by its
    ``_control_classifier`` attribute (curtailable, dispatchable, or storage).

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
        tech_config = self.options["tech_config"]

        self.n_timesteps = plant_config["plant"]["simulation"]["n_timesteps"]
        plant_config.get("technology_interconnections", [])
        technologies = tech_config.get("technologies", {})

        # ---- 1. Identify the (single) demand technology from tech_config ----
        # A demand tech has "Demand" in its performance model name.
        self.commodity = None
        self.demand_profile = None
        self.commodity_units = None
        for tech_name, tech_def in technologies.items():
            model_name = tech_def.get("performance_model", {}).get("model", "")
            if "Demand" not in model_name:
                continue

            model_inputs = tech_def.get("model_inputs", {})
            perf_params = model_inputs.get("performance_parameters", {})
            shared_params = model_inputs.get("shared_parameters", {})
            all_params = {**shared_params, **perf_params}

            if self.commodity is not None:
                raise ValueError(
                    "SystemLevelControl currently supports only one demand "
                    f"stream, but found demands for both '{self.commodity}' "
                    f"and '{all_params.get('commodity', tech_name)}'."
                )
            self.commodity = all_params["commodity"]
            self.commodity_units = all_params.get("commodity_rate_units", None)
            self.demand_profile = all_params.get("demand_profile", 0.0)
            self.demand_tech = tech_name

        # Input: demand profile
        self.demand_input_name = f"{self.commodity}_demand"
        self.add_input(
            self.demand_input_name,
            val=self.demand_profile,
            shape=self.n_timesteps,
            units=self.commodity_units,
            desc=f"Demand profile of {self.commodity}",
        )

        # ---- 2. Classify technologies by _control_classifier ----
        self.curtailable_techs = []
        self.dispatchable_techs = []
        self.storage_techs = []

        for tech_name, tech_def in technologies.items():
            perf_model_name = tech_def.get("performance_model", {}).get("model", "")
            if perf_model_name not in supported_models:
                continue
            model_cls = supported_models[perf_model_name]
            classifier = getattr(model_cls, "_control_classifier", None)
            if classifier == "curtailable":
                self.curtailable_techs.append(tech_name)
            elif classifier == "dispatchable":
                self.dispatchable_techs.append(tech_name)
            elif classifier == "storage":
                self.storage_techs.append(tech_name)

        # ---- 3. Add OpenMDAO inputs / outputs ----
        # Inputs & outputs for curtailable techs
        self.curtailable_input_names = []
        self.curtailable_output_names = []
        for tech_name in self.curtailable_techs:
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
            self.curtailable_input_names.append(in_name)
            self.curtailable_output_names.append(out_name)

        # Inputs & outputs for dispatchable techs
        self.dispatchable_input_names = []
        self.dispatchable_output_names = []
        for tech_name in self.dispatchable_techs:
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
            self.dispatchable_input_names.append(in_name)
            self.dispatchable_output_names.append(out_name)

        # Inputs & outputs for storage techs
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

        # 1. Apply curtailable production first (pass through actual output)
        for in_name, out_name in zip(self.curtailable_input_names, self.curtailable_output_names):
            curtailable_output = inputs[in_name]
            outputs[out_name] = curtailable_output
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
