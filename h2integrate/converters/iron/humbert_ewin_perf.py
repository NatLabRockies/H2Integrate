"""Iron electronwinning performance model based on Humbert et al.

This module contains H2I performance configs and components for modeling iron electrowinning. It is
based on the work of Humbert et al. (doi.org/10.1007/s40831-024-00878-3) which reviews performance
and TEA literature for three different types of iron electrowinning:
    - Aqueous Hydroxide Electrolysis (AHE)
    - Molten Salt Electrolysis (MSE)
    - Molten Oxide Electrolysis (MOE)

This technology is selected in the tech_config as the performance_model
"humbert_electrowinning_performance"

Classes:
    HumbertEwinConfig: Sets the required model_inputs fields.
    HumbertEwinPerformanceComponent: Defines initialize(), setup(), and compute() methods.

"""

import numpy as np
import openmdao.api as om
from attrs import field, define

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.core.validators import contains


@define
class HumbertEwinConfig(BaseConfig):
    """Configuration class for the Humbert iron electrowinning performance model.

    Args:
        electrolysis_type (str): The type of electrowinning being performed. Options:
            "ahe": Aqueous Hydroxide Electrolysis (AHE)
            "mse": Molten Salt Electrolysis (MSE)
            "moe": Molten Oxide Electrolysis (MOE)
        ore_fe_wt_pct (float): The iron content of the ore coming in, expressed as a percentage.
        capacity_mw (float): The MW electrical capacity of the electrowinning plant.

    """

    electrolysis_type: str = field(
        kw_only=True, converter=(str.lower, str.strip), validator=contains(["ahe", "mse", "moe"])
    )  # product selection
    ore_fe_wt_pct: float = field(kw_only=True)
    capacity_mw: float = field(kw_only=True)


class HumbertEwinPerformanceComponent(om.ExplicitComponent):
    """OpenMDAO component for the Humbert iron electrowinning performance model.

    Attributes:
        OpenMDAO Inputs:

        electricity_in (array): Electric power input available in kW for each timestep.
        iron_ore_in (array): Iron ore mass flow available in kg/h for each timestep.
        ore_fe_concentration (float): The iron content of the ore coming in, given as a percentage.
        spec_energy_cons_fe (float): The specific electrical energy consumption required to win
            pure iron (Fe) from iron ore. These are currently calculated as averages between the
            high and low stated values in Table 10 of Humbert et al., but this is exposed as an
            OpenMDAO variable to probe the effect of specific energy consumption on iron cost.
        capacity (float): The electrical capacity of the electrowinning plant in MW.

        OpenMDAO Outputs:

        electricity_consumed (array): Electric power consumption in kW for each timestep.
        limiting_input (array): An array of integers indicating which input is the limiting factor
            for iron production at each timestep: 0 = iron ore, 1 = electricity, 2 = capacity
        sponge_iron_out (array): Sponge iron production in kg/h for each timestep.
        total_sponge_iron_produced (float): Total annual sponge iron production in kg/y.
        output_capacity (float): Maximum possible annual sponge iron production in kg/y.

    """

    def initialize(self):
        self.options.declare("driver_config", types=dict)
        self.options.declare("plant_config", types=dict)
        self.options.declare("tech_config", types=dict)

    def setup(self):
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]
        self.config = HumbertEwinConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance"),
            strict=False,
        )

        ewin_type = self.config.electrolysis_type
        # Look up performance parameters for each electrolysis type from Humbert Table 10
        if ewin_type == "ahe":
            E_all_lo = 2.781
            E_all_hi = 3.779
            E_electrolysis_lo = 1.869
            E_electrolysis_hi = 2.72
        elif ewin_type == "mse":
            E_all_lo = 2.720
            E_all_hi = 3.138
            E_electrolysis_lo = 1.81
            E_electrolysis_hi = 2.08
        elif ewin_type == "moe":
            E_all_lo = 2.89
            E_all_hi = 4.45
            E_electrolysis_lo = 2.89
            E_electrolysis_hi = 4.45
        E_all = (E_all_lo + E_all_hi) / 2  # kWh/kg_Fe
        E_electrolysis = (E_electrolysis_lo + E_electrolysis_hi) / 2  # kWh/kg_Fe

        self.add_input("electricity_in", val=0.0, shape=n_timesteps, units="kW")
        self.add_input("iron_ore_in", val=0.0, shape=n_timesteps, units="kg/h")
        self.add_input("ore_fe_concentration", val=self.config.ore_fe_wt_pct, units="percent")
        self.add_input("spec_energy_all", val=E_all, units="kW*h/kg")
        self.add_input("spec_energy_electrolysis", val=E_electrolysis, units="kW*h/kg")
        self.add_input("capacity", val=self.config.capacity_mw, units="MW")

        self.add_output(
            "electricity_consumed",
            val=0.0,
            shape=n_timesteps,
            units="kW",
            desc="Electricity consumed",
        )
        self.add_output("limiting_input", val=0.0, shape=n_timesteps, units=None)
        self.add_output("sponge_iron_out", val=0.0, shape=n_timesteps, units="kg/h")
        self.add_output("total_sponge_iron_produced", val=0.0, units="kg/year")
        self.add_output("output_capacity", val=0.0, units="kg/year")
        self.add_output("specific_energy_electrolysis", val=0.0, units="kW*h/kg")

    def compute(self, inputs, outputs):
        self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]

        # Parse inputs
        elec_in = inputs["electricity_in"]
        ore_in = inputs["iron_ore_in"]
        pct_fe = inputs["ore_fe_concentration"]
        kwh_kg_fe = inputs["spec_energy_all"]
        kwh_kg_electrolysis = inputs["spec_energy_electrolysis"]
        cap_kw = inputs["capacity"] * 1000

        # Calculate max iron production for each input
        fe_from_ore = ore_in * pct_fe / 100
        fe_from_elec = elec_in / kwh_kg_fe

        # Limit iron production per hour by each input
        fe_prod = np.minimum.reduce([fe_from_ore, fe_from_elec])

        # If production is limited by available ore at any timestep i, limiters[i] = 0
        # If limited by electricity, limiters[i] = 1
        limiters = np.argmin([fe_from_ore, fe_from_elec], axis=0)

        # Limiting iron production per hour by capacity
        fe_prod = np.minimum.reduce([fe_prod, np.full(len(fe_prod), cap_kw / kwh_kg_fe)])

        # If capacity limits production at any timestep i, cap_lim[i] = 1
        # Otherwise, cap_lim[i] = 0
        cap_lim = 1 - np.argmax([fe_prod, np.full(len(fe_prod), cap_kw / kwh_kg_fe)], axis=0)

        # Determine what the limiting factor is for each hour
        # At each timestep: 0 = iron ore, 1 = electricity, 2 = capacity
        limiters = np.maximum.reduce([cap_lim * 2, limiters])
        outputs["limiting_input"] = limiters

        # Determine actual electricity consumption from iron consumption
        elec_consume = fe_prod * kwh_kg_fe

        # Return iron production
        outputs["sponge_iron_out"] = fe_prod
        outputs["electricity_consumed"] = elec_consume
        outputs["total_sponge_iron_produced"] = np.sum(fe_prod)
        outputs["output_capacity"] = cap_kw / kwh_kg_fe * 8760
        outputs["specific_energy_electrolysis"] = kwh_kg_electrolysis
