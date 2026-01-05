import hashlib
from pathlib import Path

import dill
import numpy as np
from hopp.tools.dispatch.plot_tools import plot_battery_output, plot_generation_profile

from h2integrate.core.utilities import CostModelBaseConfig
from h2integrate.core.model_baseclasses import CostModelBaseClass
from h2integrate.converters.hopp.hopp_mgmt import run_hopp, setup_hopp


class HOPPComponent(CostModelBaseClass):
    """
    A simple OpenMDAO component that represents a HOPP model.

    This component uses caching to store and retrieve results of the HOPP model
    based on the configuration and project lifetime. The caching mechanism helps
    to avoid redundant computations and speeds up the execution by reusing previously
    computed results when the same configuration is encountered.
    """

    def setup(self):
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]
        dt = self.options["plant_config"]["plant"]["simulation"]["dt"]
        config_dict = {
            "cost_year": self.options["tech_config"]["model_inputs"]["cost_parameters"]["cost_year"]
        }
        self.config = CostModelBaseConfig.from_dict(config_dict)
        super().setup()

        self.hopp_config = self.options["tech_config"]["performance_model"]["config"]

        if "simulation_options" in self.hopp_config["config"]:
            if "cache" in self.hopp_config["config"]["simulation_options"]:
                self.cache = self.hopp_config["config"]["simulation_options"]["cache"]
            else:
                self.cache = True
        else:
            self.cache = True

        if "wind" in self.hopp_config["technologies"]:
            wind_turbine_rating_kw_init = self.hopp_config["technologies"]["wind"].get(
                "turbine_rating_kw", 0.0
            )
            self.add_input("wind_turbine_rating_kw", val=wind_turbine_rating_kw_init, units="kW")

        if "pv" in self.hopp_config["technologies"]:
            pv_capacity_kw_init = self.hopp_config["technologies"]["pv"].get(
                "system_capacity_kw", 0.0
            )
            self.add_input("pv_capacity_kw", val=pv_capacity_kw_init, units="kW")

        if "battery" in self.hopp_config["technologies"]:
            battery_capacity_kw_init = self.hopp_config["technologies"]["battery"].get(
                "system_capacity_kw", 4140.0
            )
            self.add_input("battery_capacity_kw", val=battery_capacity_kw_init, units="kW")

            battery_capacity_kwh_init = self.hopp_config["technologies"]["battery"].get(
                "system_capacity_kwh", 0.0
            )
            self.add_input("battery_capacity_kwh", val=battery_capacity_kwh_init, units="kW*h")

        # Outputs
        self.add_output("percent_load_missed", units="percent", val=0.0)
        self.add_output("curtailment_percent", units="percent", val=0.0)
        self.add_output("aep", units="kW*h", val=0.0)
        self.add_output(
            "electricity_out", val=np.zeros(n_timesteps), units=f"kW*({dt}*s)", desc="Power output"
        )
        self.add_output("battery_duration", val=0.0, units="h", desc="Battery duration")
        self.add_output(
            "annual_energy_to_interconnect_potential_ratio",
            val=0.0,
            units="unitless",
            desc="Annual energy to interconnect potential ratio",
        )
        self.add_output(
            "power_capacity_to_interconnect_ratio",
            val=0.0,
            units="unitless",
            desc="Power capacity to interconnect ratio",
        )

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        # Define the keys of interest from the HOPP results that we want to cache
        keys_of_interest = [
            "percent_load_missed",
            "curtailment_percent",
            "combined_hybrid_power_production_hopp",
            "annual_energies",
            "capex",
            "opex",
        ]

        if self.cache:
            # Create a unique hash for the current configuration to use as a cache key
            config_hash = hashlib.md5(
                str(self.options["tech_config"]["performance_model"]["config"]).encode("utf-8")
                + str(self.options["plant_config"]["plant"]["plant_life"]).encode("utf-8")
            ).hexdigest()

            # Create a cache directory if it doesn't exist
            cache_dir = Path("cache")
            if not cache_dir.exists():
                cache_dir.mkdir(parents=True)
            cache_file = f"cache/{config_hash}.pkl"

        # Check if the results for the current configuration are already cached
        if self.cache and Path(cache_file).exists():
            # Load the cached results
            cache_path = Path(cache_file)
            with cache_path.open("rb") as f:
                subset_of_hopp_results = dill.load(f)
        else:
            electrolyzer_rating = None
            if "electrolyzer_rating" in self.options["tech_config"]:
                electrolyzer_rating = self.options["tech_config"]["electrolyzer_rating"]

            if "pv" in self.hopp_config["technologies"]:
                pv_capacity_kw = inputs["pv_capacity_kw"][0]
            else:
                pv_capacity_kw = None

            if "battery" in self.hopp_config["technologies"]:
                battery_capacity_kw = inputs["battery_capacity_kw"][0]
                battery_capacity_kwh = inputs["battery_capacity_kwh"][0]
            else:
                battery_capacity_kw = None
                battery_capacity_kwh = None

            if "wind" in self.hopp_config["technologies"]:
                wind_turbine_rating_kw = inputs["wind_turbine_rating_kw"][0]
            else:
                wind_turbine_rating_kw = None

            self.hybrid_interface = setup_hopp(
                hopp_config=self.options["tech_config"]["performance_model"]["config"],
                wind_turbine_rating_kw=wind_turbine_rating_kw,
                pv_rating_kw=pv_capacity_kw,
                battery_rating_kw=battery_capacity_kw,
                battery_rating_kwh=battery_capacity_kwh,
                electrolyzer_rating=electrolyzer_rating,
                n_timesteps=self.options["plant_config"]["plant"]["simulation"]["n_timesteps"],
            )

            # Run the HOPP model and get the results
            hopp_results = run_hopp(
                self.hybrid_interface,
                self.options["plant_config"]["plant"]["plant_life"],
                n_timesteps=self.options["plant_config"]["plant"]["simulation"]["n_timesteps"],
            )
            # Extract the subset of results we are interested in
            subset_of_hopp_results = {key: hopp_results[key] for key in keys_of_interest}
            # Cache the results for future use
            if self.cache:
                cache_path = Path(cache_file)
                with cache_path.open("wb") as f:
                    dill.dump(subset_of_hopp_results, f)

            try:
                system = self.hybrid_interface.system
                plot_battery_output(system, start_day=180, plot_filename="battery_output.png")
                plot_generation_profile(
                    system, start_day=180, plot_filename="generation_profile.png"
                )
            except AttributeError:
                pass

        # Set the outputs from the cached or newly computed results
        outputs["percent_load_missed"] = subset_of_hopp_results["percent_load_missed"]
        outputs["curtailment_percent"] = subset_of_hopp_results["curtailment_percent"]
        outputs["aep"] = subset_of_hopp_results["annual_energies"]["hybrid"]
        outputs["electricity_out"] = subset_of_hopp_results["combined_hybrid_power_production_hopp"]
        outputs["CapEx"] = subset_of_hopp_results["capex"]
        outputs["OpEx"] = subset_of_hopp_results["opex"]

        if "battery" in self.hopp_config["technologies"]:
            outputs["battery_duration"] = (
                inputs["battery_capacity_kwh"] / inputs["battery_capacity_kw"]
            )

        if "desired_schedule" in self.hopp_config["site"]:
            uphours = np.count_nonzero(self.hopp_config["site"]["desired_schedule"])
        else:
            uphours = 8760
        interconnect_kw = self.hopp_config["technologies"]["grid"]["interconnect_kw"]
        interconnect_kwh = interconnect_kw * uphours
        outputs["annual_energy_to_interconnect_potential_ratio"] = outputs["aep"] / interconnect_kwh

        total_power_capacity = 0.0
        for tech, tech_conf in self.hopp_config["technologies"].items():
            if tech == "wind":
                num_turbines = tech_conf.get("num_turbines", 0)
                turbine_rating_kw = tech_conf.get("turbine_rating_kw", 0.0)
                total_power_capacity += num_turbines * turbine_rating_kw
            elif tech != "grid":
                total_power_capacity += tech_conf.get("system_capacity_kw", 0.0)

        outputs["power_capacity_to_interconnect_ratio"] = total_power_capacity / interconnect_kw
