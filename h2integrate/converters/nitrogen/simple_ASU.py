import numpy as np
import openmdao.api as om
from attrs import field, define

from h2integrate.core.utilities import BaseConfig, CostModelBaseConfig, merge_shared_inputs
from h2integrate.core.validators import contains, range_val
from h2integrate.tools.constants import N_MW, AR_MW, O2_MW
from h2integrate.core.model_baseclasses import CostModelBaseClass


@define(kw_only=True)
class SimpleASUPerformanceConfig(BaseConfig):
    """Configuration for ASU model. To represent a cryogenic ASU, it is
    recommended to set the parameter `efficiency_kWh_pr_kg_N2` to 0.119.
    To represent a pressure swing absorption ASU, it is
    recommended to set the parameter `efficiency_kWh_pr_kg_N2` to 0.29.

    Attributes:
        size_from_N2_demand (bool): if True, size the system based on some input demand. If False,
            size the system from user input (`rated_N2_kg_pr_hr` or `ASU_rated_power_kW`).
        rated_N2_kg_pr_hr (float | None): Rated capacity of ASU in kg-N2/hour. Only required if
            `size_from_N2_demand` is False and ASU_rated_power_kW is not input.
        ASU_rated_power_kW (float | None): Rated capacity of ASU in kg-N2/hour. Only required if
            `size_from_N2_demand` is False and `rated_N2_kg_pr_hr` is not input.
        efficiency_kWh_pr_kg_N2 (float): efficiency of the ASU in kWh/kg-N2, defaults to 0.29.
            Should be between 0.1 and 0.5. Some reference efficiencies are::
                - 0.29 for pressure swing absorption
                - 0.119 for cryogenic
        N2_fraction_in_air (float, optional): nitrogen content of input air stream as mole fraction.
            Defaults to 0.7811.
        O2_fraction_in_air (float, optional): oxygen content of input air stream as mole fraction.
            Defaults to 0.2096.
        Ar_fraction_in_air (float, optional): argon content of input air stream as mole fraction.
            Defaults to 0.0093.
    """

    size_from_N2_demand: bool = field()
    rated_N2_kg_pr_hr: float | None = field(default=None)
    ASU_rated_power_kW: float | None = field(default=None)

    N2_fraction_in_air: float = field(default=0.7811, validator=range_val(0, 1))
    O2_fraction_in_air: float = field(default=0.2096, validator=range_val(0, 1))
    Ar_fraction_in_air: float = field(default=0.0093, validator=range_val(0, 1))
    efficiency_kWh_pr_kg_N2: float = field(default=0.29, validator=range_val(0.10, 0.50))
    # 0.29 is efficiency of pressure swing absorption
    # 0.119 is efficiency of cryogenic

    def __attrs_post_init__(self):
        if (not self.size_from_N2_demand) and (
            self.rated_N2_kg_pr_hr is None and self.ASU_rated_power_kW is None
        ):
            msg = (
                "Either rated_N2_kg_pr_hr or ASU_rated_power_kW must be input if "
                "size_from_N2_demand is False"
            )
            raise ValueError(msg)


class SimpleASUPerformanceModel(om.ExplicitComponent):
    """Simple linear converter to model nitrogen production from an
    Air Separation Unit.
    """

    def initialize(self):
        self.options.declare("plant_config", types=dict)
        self.options.declare("tech_config", types=dict)
        self.options.declare("driver_config", types=dict)

    def setup(self):
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]
        self.config = SimpleASUPerformanceConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance")
        )
        if self.config.size_from_N2_demand:
            self.add_input("nitrogen_in", val=0.0, shape=n_timesteps, units="kg/h")
            self.add_output("electricity_in", val=0.0, shape=n_timesteps, units="kW")

        else:
            self.add_input("electricity_in", val=0.0, shape=n_timesteps, units="kW")

        self.add_output("air_in", val=0.0, shape=n_timesteps, units="kg/h")
        self.add_output("ASU_capacity_kW", val=0.0, units="kW", desc="ASU rated capacity in kW")
        self.add_output(
            "rated_N2_kg_pr_hr", val=0.0, units="kg/h", desc="ASU rated capacity in kg-N2/hour"
        )

        self.add_output(
            "annual_electricity_consumption",
            val=0.0,
            units="kW",
            desc="ASU annual electricity consumption in kWh/year",
        )
        self.add_output(
            "total_nitrogen_produced",
            val=0.0,
            units="kg/year",
            desc="ASU annual nitrogen production in kg-N2/year",
        )
        self.add_output(
            "annual_max_nitrogen_production",
            val=0.0,
            units="kg/year",
            desc="ASU maximum annual nitrogen production in kg-N2/year",
        )
        self.add_output(
            "nitrogen_production_capacity_factor",
            val=0.0,
            units=None,
            desc="ASU annual nitrogen production in kg-N2/year",
        )

        self.add_output("nitrogen_out", val=0.0, shape=n_timesteps, units="kg/h")
        self.add_output("oxygen_out", val=0.0, shape=n_timesteps, units="kg/h")
        self.add_output("argon_out", val=0.0, shape=n_timesteps, units="kg/h")

    def compute(self, inputs, outputs):
        """Calculate the amount of N2 that can be produced and the amount of feedstocks required
        given the input parameters and values.

        Args:
            inputs (dict): input variables/parameters
            outputs (dict: output variables/parameters

        Raises:
            ValueError: if user provided ASU capacities in kg-N2/hour and kW and
                these values do not result in the same efficiency as `efficiency_kWh_pr_kg_N2`.
        """

        if self.config.size_from_N2_demand:
            # Size the ASU to based on the maximum hourly nitrogen demand.
            rated_N2_kg_pr_hr = np.max(inputs["nitrogen_in"])
            n2_profile_in_kg = inputs["nitrogen_in"]
            ASU_rated_power_kW = rated_N2_kg_pr_hr * self.config.efficiency_kWh_pr_kg_N2
        else:
            n2_profile_in_kg = inputs["electricity_in"] / self.config.efficiency_kWh_pr_kg_N2
            provided_kW_not_kg = (
                self.config.ASU_rated_power_kW is not None and self.config.rated_N2_kg_pr_hr is None
            )
            provided_kg_not_kW = (
                self.config.ASU_rated_power_kW is None and self.config.rated_N2_kg_pr_hr is not None
            )
            provided_both = (
                self.config.ASU_rated_power_kW is not None
                and self.config.rated_N2_kg_pr_hr is not None
            )
            if provided_kW_not_kg:
                # calculate capacity in kg-N2/hour based on user-provided capacity in kW
                rated_N2_kg_pr_hr = (
                    self.config.ASU_rated_power_kW / self.config.efficiency_kWh_pr_kg_N2
                )
                ASU_rated_power_kW = self.config.ASU_rated_power_kW
            if provided_kg_not_kW:
                # calculate capacity in kW based on user-provided capacity in kg-N2/hour
                rated_N2_kg_pr_hr = self.config.rated_N2_kg_pr_hr
                ASU_rated_power_kW = (
                    self.config.rated_N2_kg_pr_hr * self.config.efficiency_kWh_pr_kg_N2
                )
            if provided_both:
                # check that user-provided capacities in kg-N2/hour and kW result
                # in the same efficiency
                rated_N2_kg_pr_hr = self.config.rated_N2_kg_pr_hr
                ASU_rated_power_kW = self.config.ASU_rated_power_kW
                if ASU_rated_power_kW / rated_N2_kg_pr_hr != self.config.efficiency_kWh_pr_kg_N2:
                    msg = (
                        f"User defined size for ASU system ({ASU_rated_power_kW} kg N2/hour at "
                        f"{rated_N2_kg_pr_hr} kW) has an efficiency of "
                        f"{ASU_rated_power_kW/rated_N2_kg_pr_hr} kWh/kg-N2, this does not "
                        f"match the ASU efficiency of {self.config.efficiency_kWh_pr_kg_N2}"
                    )
                    raise ValueError(msg)

        # calculate the molar mass of air
        air_molar_mass = (
            (2 * N_MW * self.config.N2_fraction_in_air)
            + (O2_MW * self.config.O2_fraction_in_air)
            + (AR_MW * self.config.Ar_fraction_in_air)
        )

        # NOTE: here is where any operational constraints would be applied to limit the N2 output

        # saturate N2 production at rated flow rate
        n2_profile_out_kg = np.where(
            n2_profile_in_kg > rated_N2_kg_pr_hr, rated_N2_kg_pr_hr, n2_profile_in_kg
        )

        # calculate air feedstock required to produce nitrogen
        n2_profile_out_mol = n2_profile_out_kg * 1e3 / N_MW
        air_profile_mol = n2_profile_out_mol / (self.config.N2_fraction_in_air)

        # calculate the secondary outputs of the ASU (O2 and Ar)
        o2_profile_mol = air_profile_mol * (self.config.O2_fraction_in_air)
        ar_profile_mol = air_profile_mol * (self.config.Ar_fraction_in_air)

        # convert air, O2, and Ar from moles into kg
        air_profile_kg = air_profile_mol * air_molar_mass / 1e3
        o2_profile_kg = o2_profile_mol * O2_MW / 1e3
        ar_profile_kg = ar_profile_mol * AR_MW / 1e3

        # calculate the electricity feedstock required to produce nitrogen
        electricity_kWh = n2_profile_out_kg * self.config.efficiency_kWh_pr_kg_N2

        # calculate the annual rated production of nitrogen in kg-N2/year
        max_annual_N2 = rated_N2_kg_pr_hr * len(n2_profile_out_kg)
        outputs["rated_N2_kg_pr_hr"] = rated_N2_kg_pr_hr  # rated ASU capacity in kg-N2/hour
        outputs["ASU_capacity_kW"] = ASU_rated_power_kW  # rated ASU capacity in kW
        outputs["air_in"] = air_profile_kg  # air feedstock profile in kg/hour
        outputs["oxygen_out"] = o2_profile_kg  # O2 secondary output profile in kg/hour
        outputs["argon_out"] = ar_profile_kg  # Ar secondary output profile in kg/hour
        outputs["nitrogen_out"] = n2_profile_out_kg  # N2 primary output profile in kg/hour

        # capacity factor of ASU
        outputs["nitrogen_production_capacity_factor"] = sum(n2_profile_out_kg) / max_annual_N2
        # annual N2 production in kg-N2/year
        outputs["total_nitrogen_produced"] = sum(n2_profile_out_kg)
        # maximum annual N2 production in kg-N2/year
        outputs["annual_max_nitrogen_production"] = max_annual_N2
        # annual electricity consumption in kWh/year
        outputs["annual_electricity_consumption"] = sum(electricity_kWh)

        if self.config.size_from_N2_demand:
            # electricity feedstock profile required to produce N2
            outputs["electricity_in"] = electricity_kWh


def make_cost_unit_multiplier(unit_str):
    """
    Returns a conversion multiplier and a unit type based on the provided unit string.
    The conversion multiplier converts the given unit to the base unit used in the model
    (kW for power, kg/hour for mass).

    Args:
        unit_str (str): The unit string, e.g., "kw", "mw", "kg/hour", "tonne/day", etc.

    Returns:
        tuple: (conversion_multiplier, unit_type)
            conversion_multiplier (float): Multiplier to convert the input unit to
                the model's base unit.
            unit_type (str): "power" if the unit is power-based, "mass" if mass-based.

    Notes:
        - For "mw", the multiplier converts MW to kW.
        - For daily units, the multiplier converts per day to per hour.
        - For "tonne" units, the multiplier converts tonnes to kg.
        - If unit_str is "none", returns (0.0, "power").
    """
    if unit_str == "none":
        return 0.0, "power"

    power_based_value = unit_str == "mw" or unit_str == "kw"
    conversion_multiplier = 1.0

    if power_based_value:
        if unit_str == "mw":
            conversion_multiplier = 1 / 1e3  # convert MW to kW
        return conversion_multiplier, "power"

    # convert from units to kg/hour
    if "day" in unit_str:  # convert from daily units to hourly units
        conversion_multiplier *= 1 / 24
    if "tonne" in unit_str:
        conversion_multiplier *= 1e3

    return conversion_multiplier, "mass"


@define(kw_only=True)
class SimpleASUCostConfig(CostModelBaseConfig):
    capex_usd_per_unit: float = field()

    capex_unit: str = field(
        validator=contains(["kg/hour", "kw", "mw", "tonne/hour", "kg/day", "tonne/day"]),
        converter=(str.strip, str.lower),
    )

    opex_usd_per_unit_per_year: float = field(default=0.0)
    opex_unit: str = field(
        default="none",
        validator=contains(["kg/hour", "kw", "mw", "tonne/hour", "kg/day", "tonne/day", "none"]),
        converter=(str.strip, str.lower),
    )

    def __attrs_post_init__(self):
        if self.opex_usd_per_unit_per_year > 0 and self.opex_unit == "none":
            msg = (
                "User provided opex value but did not specify units. "
                "Please specify opex_unit as one of the following: "
                "kg/hour, kw, MW, tonne/hour, kg/day, or tonne/day"
            )
            raise ValueError(msg)


class SimpleASUCostModel(CostModelBaseClass):
    def initialize(self):
        self.options.declare("plant_config", types=dict)
        self.options.declare("tech_config", types=dict)
        self.options.declare("driver_config", types=dict)

    def setup(self):
        self.config = SimpleASUCostConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost")
        )
        super().setup()

        self.add_input("ASU_capacity_kW", val=0.0, units="kW")
        self.add_input("rated_N2_kg_pr_hr", val=0.0, units="kg/h")

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        # Get config values
        capex_k, capex_based_unit = make_cost_unit_multiplier(self.config.capex_unit)
        unit_capex = self.config.capex_usd_per_unit * capex_k
        if capex_based_unit == "power":
            capex_usd = unit_capex * inputs["ASU_capacity_kW"]
        else:
            capex_usd = unit_capex * inputs["rated_N2_kg_pr_hr"]

        opex_k, opex_based_unit = make_cost_unit_multiplier(self.config.opex_unit)
        unit_opex = self.config.opex_usd_per_unit_per_year * opex_k
        if opex_based_unit == "power":
            opex_usd_per_year = unit_opex * inputs["ASU_capacity_kW"]
        else:
            opex_usd_per_year = unit_opex * inputs["rated_N2_kg_pr_hr"]

        outputs["CapEx"] = capex_usd
        outputs["OpEx"] = opex_usd_per_year
