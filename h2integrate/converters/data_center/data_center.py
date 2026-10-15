import csv
from typing import ClassVar
from pathlib import Path

import numpy as np
import eeweather
from attrs import field, define, validators

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.core.model_baseclass import (
    CostModelBaseClass,
    CostModelBaseConfig,
    PerformanceModelBaseClass,
)
from h2integrate.core.supported_models import register


@define(kw_only=True)
class DataCenterPerformanceModelConfig(BaseConfig):
    """
    Configuration class for the DataCenterPerformanceModel.

    Attributes:
        system_capacity_mw (float): Maximum compute capacity of the data center in MW.
        compute_electrical_efficiency (float): Efficiency of converting electricity to
            compute load (0 < efficiency <= 1).
        cooling_load_ratio (float): Ratio of cooling load to compute load.
        water_use_gal_per_mwh (float): Water usage per compute load in galUS/MWh.
    """

    system_capacity_mw: float = field(validator=validators.gt(0))
    compute_electrical_efficiency: float = field(validator=validators.gt(0))
    cooling_load_ratio: float = field(validator=validators.ge(0))
    water_use_gal_per_mwh: float = field(validator=validators.ge(0))
    compute_load_demand: int | float | list = field()


@register
class DataCenterPerformanceModel(PerformanceModelBaseClass):
    """
    Performance model for data centers.

    This model calculates compute output based on the compute demand and the available
    electricity. The total electricity usage is determined by an overall system electrical
    efficiency as well as an additional cooling load that is proportional to the compute load.
    The amount of water needed for cooling is also computed.

    Inputs:
        system_capacity_mw (float): Maximum compute capacity of the data center in MW.
        compute_electrical_efficiency (float): Efficiency of converting electricity to
            compute load (0 < efficiency <= 1).
        cooling_load_ratio (float): Ratio of cooling load to compute load.
        water_use_gal_per_mwh (float): Water usage per MWh of compute load.
        electricity_in (float array): Electricity input profile in MW/h.
        compute_load_demand (float array): Compute load demand profile in MW.
        water_in (float array): Water input profile in galUS/h.

    Outputs:
        compute_load_out (float array): Actual compute load output in MW.
        unmet_electricity_demand (float array): Unmet electricity demand in MW.
        water_consumed (float array): Water consumed in galUS/h.
    """

    _time_step_bounds = (
        3600,
        3600,
    )  # (min, max) time step lengths (in seconds) compatible with this model

    def initialize(self):
        super().initialize()
        self.commodity = "compute_load"
        self.commodity_rate_units = "MW"
        self.commodity_amount_units = "MW*h"

    def setup(self):
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]
        self.config = DataCenterPerformanceModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance"),
            additional_cls_name=self.__class__.__name__,
        )
        super().setup()

        self.add_input(
            f"{self.commodity}_demand",
            val=self.config.compute_load_demand,
            shape=n_timesteps,
            units=self.commodity_rate_units,
            desc="Data center compute load demand profile",
        )

        # Add rated capacity as an input with config value as default
        self.add_input(
            "system_capacity",
            val=self.config.system_capacity_mw,
            units="MW",
            desc="Data center rated capacity in MW",
        )

        self.add_input(
            "electricity_in",
            val=0.0,
            shape=n_timesteps,
            units=self.commodity_rate_units,
            desc="Electricity input",
        )

        self.add_input(
            "water_in",
            val=0.0,
            shape=n_timesteps,
            units="galUS/h",
            desc="Water input",
        )

        self.add_output(
            "water_consumed",
            val=0.0,
            shape=n_timesteps,
            units="galUS/h",
            desc="Water consumed by the plant",
        )

        self.add_output(
            "unmet_electricity_demand",
            val=0.0,
            shape=n_timesteps,
            units=self.commodity_rate_units,
            desc="Unmet electricity demand for data center",
        )

    def compute(self, inputs, outputs, discrete_inputs=None, discrete_outputs=None):
        """
        Compute the performance of the data center.

        The computation determines the compute load output based on the input compute load demand,
        available electricity, and the data center's electrical efficiency and cooling load ratio.
        It also calculates any unmet electricity demand and water consumption.

        Args:
            inputs: OpenMDAO inputs object containing compute_load_demand, water_in, and
                electricity_in.
            outputs: OpenMDAO outputs object for compute_load_out, water_consumed,
                and unmet_electricity_demand.
        """
        # system_capacity = self.config.system_capacity_mw  # plant capacity in MW
        # max water consumption in galUS/h
        max_water_consumption = inputs["system_capacity"] * self.config.water_use_gal_per_mwh

        # Compute load demand, saturated at maximum rated system capacity
        compute_load_demand = np.where(
            inputs["compute_load_demand"] > inputs["system_capacity"],
            inputs["system_capacity"],
            inputs["compute_load_demand"],
        )

        # Scale the electrical compute load by the electrical efficiency
        electrical_compute_load_demand = (
            compute_load_demand / self.config.compute_electrical_efficiency
        )

        # Total electricity demand is the summation of compute load and cooling load
        total_electricity_demand = (
            electrical_compute_load_demand
            + electrical_compute_load_demand * self.config.cooling_load_ratio
        )

        # Determine the amount of electricity used as the min of total demand and available input
        electricity_used = np.minimum.reduce([total_electricity_demand, inputs["electricity_in"]])

        water_demand = compute_load_demand * self.config.water_use_gal_per_mwh

        # available feedstock, saturated at maximum system feedstock consumption
        water_available = np.where(
            inputs["water_in"] > max_water_consumption,
            max_water_consumption,
            inputs["water_in"],
        )

        water_consumed = np.minimum.reduce([water_demand, water_available])

        max_production = inputs["system_capacity"] * len(compute_load_demand) * (self.dt / 3600)

        outputs["unmet_electricity_demand_out"] = total_electricity_demand - electricity_used
        outputs["water_consumed"] = water_consumed
        outputs["compute_load_out"] = compute_load_demand
        outputs["total_compute_load_produced"] = np.sum(compute_load_demand) * (self.dt / 3600)
        outputs["capacity_factor"] = outputs["total_compute_load_produced"].sum() / max_production
        outputs["annual_compute_load_produced"] = outputs["total_compute_load_produced"] * (
            1 / self.fraction_of_year_simulated
        )
        outputs["rated_compute_load_production"] = inputs["system_capacity"]


@define(kw_only=True)
class DataCenterCostModelConfig(CostModelBaseConfig):
    """
    Configuration class for the DataCenterCostModel.

    Attributes:
        system_capacity_mw (float): Maximum compute capacity of the data center in MW.
        capex_per_mw (float | int): Capital cost per unit capacity in USD/MW.
        fixed_opex_per_mw_per_year (float | int): Fixed operating expenses per unit capacity per
            year in USD/(MW*year).
        variable_opex_per_mwh (float | int): Variable operating expenses per unit generation in
            USD/(MW*h). This includes costs of electricity and water inputs.
    """

    system_capacity_mw: float = field(validator=validators.gt(0))
    capex_per_mw: float | int = field(validator=validators.ge(0))
    fixed_opex_per_mw_per_year: float | int = field(validator=validators.ge(0))
    variable_opex_per_mwh: float | int = field(validator=validators.ge(0))


@register
class DataCenterCostModel(CostModelBaseClass):
    """
    Cost model for data centers.

    This simple cost model calculates capital and operating costs for data centers, including
        costs associated with electricity and water usage.

    Cost components:
    1. Capital costs: capex_per_mw * system_capacity_mw
    2. Fixed operating expenses: fixed_opex_per_mw_per_year * system_capacity_mw
    3. Variable operating expenses: variable_opex_per_mwh * total_compute_load_MWh
    """

    _time_step_bounds = (
        3600,
        3600,
    )  # (min, max) time step lengths (in seconds) compatible with this model

    def initialize(self):
        super().initialize()
        self.commodity = "compute_load"
        self.commodity_rate_units = "MW"
        self.commodity_amount_units = "MW*h"

    def setup(self):
        self.config = DataCenterCostModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost"),
            additional_cls_name=self.__class__.__name__,
        )
        super().setup()
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]

        self.add_input(
            "system_capacity",
            val=self.config.system_capacity_mw,
            units="MW",
            desc="Data center capacity",
        )
        self.add_input(
            "compute_load_out",
            val=0.0,
            shape=n_timesteps,
            units="MW",
            desc="Hourly compute load output from performance model",
        )
        self.add_input(
            "capex_per_mw",
            val=self.config.capex_per_mw,
            units="USD/MW",
            desc="Capital cost per unit capacity",
        )
        self.add_input(
            "fixed_opex_per_mw_per_year",
            val=self.config.fixed_opex_per_mw_per_year,
            units="USD/(MW*year)",
            desc="Fixed operating expenses per unit capacity per year",
        )
        self.add_input(
            "variable_opex_per_mwh",
            val=self.config.variable_opex_per_mwh,
            units="USD/(MW*h)",
            desc="Variable operating expenses per unit generation",
        )

    def compute(self, inputs, outputs, discrete_inputs=None, discrete_outputs=None):
        """
        Compute capital and operating costs for the data center.
        """
        system_capacity_mw = self.config.system_capacity_mw
        compute_load_out = inputs["compute_load_out"]  # MW hourly profile
        capex_per_mw = inputs["capex_per_mw"]
        fixed_opex_per_mw_per_year = inputs["fixed_opex_per_mw_per_year"]
        variable_opex_per_mwh = inputs["variable_opex_per_mwh"]

        # Sum hourly compute load output to get annual generation
        # compute_load_out is in MW, so sum gives MWh for hourly data
        dt = self.options["plant_config"]["plant"]["simulation"]["dt"]
        delivered_compute_load_MWdt = compute_load_out.sum()
        delivered_compute_load_MWh = delivered_compute_load_MWdt * dt / 3600

        # Calculate capital expenditure
        capex = capex_per_mw * system_capacity_mw

        # Calculate fixed operating expenses over project life
        fixed_om = fixed_opex_per_mw_per_year * system_capacity_mw

        # Calculate variable operating expenses over project life
        variable_om = variable_opex_per_mwh * delivered_compute_load_MWh

        # Total operating expenditure includes all O&M
        opex = fixed_om + variable_om

        outputs["CapEx"] = capex
        outputs["OpEx"] = opex


@define(kw_only=True)
class DataCenterPUEWUEPerformanceModelConfig(BaseConfig):
    """
    Configuration class for the DataCenterPUEWUEPerformanceModel.

    This model uses Power Usage Effectiveness (PUE) and Water Usage Effectiveness (WUE)
    to determine the total power and water consumption from a given compute IT workload. It is
    based on the values determined in [1].

    [1] Lei, Nuoa, and Eric Masanet. "Climate-and technology-specific PUE and WUE estimations
    for US data centers using a hybrid statistical and thermodynamics-based approach."
    Resources, Conservation and Recycling 182 (2022): 106323.

    Attributes:
        compute_load_demand (float or list): Compute IT workload demand profile in MW.
        system_capacity_mw (float): Maximum compute capacity of the data center in MW.
        pue (float, optional): Power Usage Effectiveness ratio (total facility power / IT
            equipment power). Typical range: 1.1 - 3.0. A PUE of 1.5 means 1.5 kW of total
            facility power per 1 kW of IT equipment power. Defaults to None, which means PUE
            will be determined based on climate zone and efficiency level.
        wue (float, optional): Water Usage Effectiveness in liters per kWh of IT equipment power.
            Typical range: 0.3 - 2.0 L/kWh. Defaults to None, which means WUE will be determined
            based on climate zone and efficiency level.
        climate_zone (str, optional): IECC climate zone (e.g., "2A", "4B"). If PUE and WUE are
            not provided and this is None, the climate zone is determined from the site
            latitude and longitude.
        efficiency_level (str, optional): "efficient" or "inefficient". Determines whether to
            use the 5th percentile ("efficient") or 95th percentile ("inefficient") PUE/WUE
            values for the given climate zone. Defaults to "efficient".
        cooling_configuration (int, optional): Cooling configuration case (1-12) of the data
            center. Defaults to None, which selects the configuration automatically.
        optimize_for (str, optional): Optimization target, either "pue" or "wue". Defaults to "pue".
        size_sqft (float, optional): Size of the data center in square feet. Defaults to None.
    """

    compute_load_demand: int | float | list = field()
    system_capacity_mw: float = field(validator=validators.gt(0))
    pue: float = field(validator=validators.optional(validators.gt(1.0)), default=None)
    wue: float = field(validator=validators.optional(validators.ge(0)), default=None)
    climate_zone: str = field(default=None)
    efficiency_level: str = field(default="efficient")
    cooling_configuration: int = field(default=None)
    optimize_for: str = field(default="pue")
    size_sqft: float = field(default=None)

    # Mapping of cooling configuration integer to description
    COOLING_CONFIGURATIONS: ClassVar[dict[int, str]] = {
        1: "Large-scale DC; Airside economizer + adiabatic cooling + (water-cooled chiller)",
        2: "Large-scale DC; Waterside economizer + (water-cooled chiller)",
        3: "Midsize DC; Airside economizer + (water-cooled chiller)",
        4: "Midsize DC; Waterside economizer + (water-cooled chiller)",
        5: "Midsize DC; Water-cooled chiller",
        6: "Midsize DC; Airside economizer + (air-cooled chiller)",
        7: "Midsize DC; Air-cooled chiller",
        8: "Small DC; Water-cooled chiller",
        9: "Small DC; Air-cooled chiller",
        10: "Small DC; Direct expansion system",
        # Direct-to-chip liquid cooling variants. "Air-cooled" here refers to the
        # heat-reject side (dry cooler); "water-cooled" uses a water-cooled
        # chiller / cooling tower. In both cases the primary ITE loop is warm
        # water in direct contact with the chip cold plates.
        11: (
            "Liquid-cooled DC; Direct-to-chip liquid loop + dry cooling + adiabatic cooling"
            " + (air-cooled chiller)"
        ),
        12: (
            "Liquid-cooled DC; Direct-to-chip liquid loop + waterside economizer"
            " + (water-cooled chiller)"
        ),
    }

    # Cooling configuration cases valid for each data center size category.
    # Large-scale: > 20,000 sqft; Midsize: 1,000-20,000 sqft; Small: < 1,000 sqft
    # Liquid-cooled cases 11-12 are applicable to both large and midsize builds.
    SIZE_COOLING_CONFIGURATIONS: ClassVar[dict[str, list[int]]] = {
        "large": [1, 2, 11, 12],
        "midsize": [3, 4, 5, 6, 7, 11, 12],
        "small": [8, 9, 10],
    }

    # Square-footage thresholds for size classification
    LARGE_SQFT_THRESHOLD = 20_000
    SMALL_SQFT_THRESHOLD = 1_000

    def __attrs_post_init__(self):
        # Check to see if the user has provided either PUE/WUE or climate zone (but not both).
        # It is also allowed to supply neither, in which case the climate zone is inferred
        # from the site's latitude/longitude at setup time.
        has_pue = self.pue is not None
        has_wue = self.wue is not None
        has_climate_zone = self.climate_zone is not None

        if has_pue != has_wue:
            missing = "wue" if has_pue else "pue"
            provided = "pue" if has_pue else "wue"
            raise ValueError(
                f"Both 'pue' and 'wue' must be provided together, but only '{provided}' was "
                f"supplied. Provide '{missing}' as well, or omit both and supply 'climate_zone' "
                f"instead (or omit all three to infer the climate zone from the site "
                f"latitude/longitude)."
            )

        if has_pue and has_climate_zone:
            raise ValueError("Provide either 'pue'/'wue' or 'climate_zone', not both.")


@register
class DataCenterPUEWUEPerformanceModel(PerformanceModelBaseClass):
    """
    Performance model for data centers using Power Usage Effectiveness (PUE) and
    Water Usage Effectiveness (WUE).

    This model calculates total facility power and water consumption based on a provided
    compute IT workload, using industry-standard PUE and WUE metrics.

    PUE = Total Facility Power / IT Equipment Power
    WUE = Water Used / IT Equipment Power Output

    Inputs:
        pue (float): Power Usage Effectiveness ratio (typically 1.1 - 3.0).
        wue (float): Water Usage Effectiveness in liters per kWh.
        compute_load_demand (float array): Compute IT workload in MW.
        system_capacity_mw (float): Maximum capacity in MW.
        electricity_in (float array): Available electricity in MW.
        water_in (float array): Available water in galUS/h.

    Outputs:
        total_facility_power (float array): Total facility power consumption in MW.
        water_used (float array): Total water consumption in galUS/h.
        unmet_electricity_demand (float array): Unmet electricity demand in MW.
        unmet_water_demand (float array): Unmet water demand in galUS/h.
    """

    _time_step_bounds = (
        3600,
        3600,
    )  # (min, max) time step lengths (in seconds) compatible with this model

    def initialize(self):
        super().initialize()
        self.commodity = "compute_load"
        self.commodity_rate_units = "MW"
        self.commodity_amount_units = "MW*h"

    def setup(self):
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]
        self.config = DataCenterPUEWUEPerformanceModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance"),
            additional_cls_name=self.__class__.__name__,
        )

        # When the user did not supply a climate zone (and did not supply PUE/WUE either),
        # infer it from the site's latitude/longitude in the plant config.
        if self.config.pue is None and self.config.climate_zone is None:
            try:
                site = self.options["plant_config"]["sites"]["site"]
                latitude = site["latitude"]
                longitude = site["longitude"]
            except (KeyError, TypeError) as err:
                raise ValueError(
                    "Could not resolve PUE/WUE: neither 'pue'/'wue' nor 'climate_zone' were "
                    "supplied, and the plant configuration does not contain "
                    "sites.site.latitude/longitude for climate-zone lookup. Supply one of these."
                ) from err
            self.config.climate_zone = self.determine_iecc_climate_zone(latitude, longitude)

        # When the user did not supply PUE/WUE directly, look them up from the
        # Lei & Masanet climate-zone dataset. When ``cooling_configuration`` is
        # not set either, the auto-selected case is stored back on the config.
        if self.config.pue is None:
            pue, wue, case_num = self.determine_pue_wue_by_climate_zone(
                climate_zone=self.config.climate_zone,
                efficiency=self.config.efficiency_level,
                cooling_configuration=self.config.cooling_configuration,
                optimize_for=self.config.optimize_for,
                size_sqft=self.config.size_sqft,
            )
            self.config.pue = pue
            self.config.wue = wue
            if self.config.cooling_configuration is None:
                self.config.cooling_configuration = case_num

        super().setup()

        # Inputs
        self.add_input(
            "compute_load_demand",
            val=self.config.compute_load_demand,
            shape=n_timesteps,
            units="MW",
            desc="Compute IT workload demand profile",
        )

        self.add_input(
            "system_capacity",
            val=self.config.system_capacity_mw,
            units="MW",
            desc="Data center rated IT capacity in MW",
        )

        self.add_input(
            "pue",
            val=self.config.pue,
            units="unitless",
            desc="Power Usage Effectiveness (total facility power / IT equipment power)",
        )

        self.add_input(
            "wue",
            val=self.config.wue,
            units="L/kW/h",
            desc="Water Usage Effectiveness (liters per kWh of IT equipment power)",
        )

        self.add_input(
            "electricity_in",
            val=0.0,
            shape=n_timesteps,
            units="MW",
            desc="Available electricity input",
        )

        self.add_input(
            "water_in",
            val=0.0,
            shape=n_timesteps,
            units="galUS/h",
            desc="Water input",
        )

        # Outputs
        self.add_output(
            "total_facility_power",
            val=0.0,
            shape=n_timesteps,
            units="MW",
            desc="Total facility power consumption (includes cooling, etc.)",
        )

        self.add_output(
            "water_consumed",
            val=0.0,
            shape=n_timesteps,
            units="galUS/h",
            desc="Water consumed by the data center",
        )

        self.add_output(
            "unmet_electricity_demand",
            val=0.0,
            shape=n_timesteps,
            units="MW",
            desc="Unmet electricity demand",
        )

        self.add_output(
            "unmet_water_demand",
            val=0.0,
            shape=n_timesteps,
            units="galUS/h",
            desc="Unmet water demand",
        )

    def compute(self, inputs, outputs, discrete_inputs=None, discrete_outputs=None):
        """
        Compute the total facility power and water consumption for the data center.

        Calculation steps:
        1. Cap IT workload at system capacity
        2. Calculate total facility power = IT workload * PUE
        3. Check electricity availability
        4. Convert IT workload to kWh and multiply by WUE to get liters
        5. Convert liters to gallons (1 gallon = 3.785 liters)
        6. Check water availability
        7. Track unmet demands
        """
        # Get inputs
        it_workload = inputs["compute_load_demand"]  # MW
        system_capacity = inputs["system_capacity"]  # MW
        pue = inputs["pue"]
        wue = inputs["wue"]  # L/kWh
        water_available = inputs["water_in"]  # galUS/h

        # Cap IT workload at system capacity
        capped_it_workload = np.minimum(it_workload, system_capacity)

        # Calculate total facility power demand using PUE
        # Total facility power = IT workload * PUE
        total_facility_power = capped_it_workload * pue  # MW

        # Track unmet electricity demand for grid set point
        electricity_available = inputs["electricity_in"]  # MW
        unmet_electricity = np.maximum(0.0, total_facility_power - electricity_available)

        # Calculate water demand using WUE
        # WUE is in L/kWh, so convert IT workload from MW to kWh
        # IT workload in MW * dt(seconds) / 3600(sec/hour) = IT workload in MW*h
        # MW*h = MWh, and 1 MWh = 1000 kWh
        it_workload_kwh = capped_it_workload * (self.dt / 3600) * 1000  # kWh per timestep
        water_demand_liters = it_workload_kwh * wue  # liters per timestep

        # Convert liters to gallons (1 gallon = 3.785 liters)
        liters_per_gallon = 3.785
        water_demand_gal = water_demand_liters / liters_per_gallon  # galUS

        # Normalize water demand back to rate (galUS/h) by dividing by dt and multiplying by 3600
        water_demand_rate = water_demand_gal / (self.dt / 3600)  # galUS/h

        # Check water availability
        water_consumed = np.minimum(water_demand_rate, water_available)
        unmet_water = water_demand_rate - water_consumed

        # Set outputs
        outputs["total_facility_power"] = total_facility_power
        outputs["water_consumed"] = water_consumed
        outputs["unmet_electricity_demand"] = unmet_electricity
        outputs["unmet_water_demand"] = unmet_water
        outputs["compute_load_out"] = capped_it_workload

        # Compute summary metrics using base-class standard output names
        outputs["total_compute_load_produced"] = np.sum(capped_it_workload) * (self.dt / 3600)
        outputs["annual_compute_load_produced"] = outputs["total_compute_load_produced"] * (
            1 / self.fraction_of_year_simulated
        )
        outputs["rated_compute_load_production"] = system_capacity
        max_production = system_capacity * len(it_workload) * (self.dt / 3600)
        outputs["capacity_factor"] = (
            outputs["total_compute_load_produced"] / max_production if max_production > 0 else 0
        )

    def determine_iecc_climate_zone(self, latitude, longitude):
        """
        Determine the IECC climate zone based on latitude and longitude.

        Uses the eeweather library to identify the nearest weather station for the given
        location and retrieves its IECC climate zone and moisture regime classification.

        Args:
            latitude (float): Latitude of the location.
            longitude (float): Longitude of the location.

        Returns:
            str: The IECC climate zone for the given location (e.g., "2A", "4B").
        """
        ranked_stations = eeweather.rank_stations(latitude, longitude)
        station, warnings = eeweather.select_station(ranked_stations)
        iecc_zone = station.iecc_climate_zone
        iecc_moisture = station.iecc_moisture_regime

        if warnings:
            raise UserWarning(
                "Warnings encountered when selecting weather station for location "
                f"({latitude}, {longitude}): {warnings}"
            )

        # IECC zones 7 and 8 do not use a moisture-regime suffix.
        return f"{iecc_zone}{iecc_moisture}" if iecc_moisture else str(iecc_zone)

    def _classify_size(self, size_sqft):
        """Return "large", "midsize", or "small" based on floor area in square feet."""
        if size_sqft > self.config.LARGE_SQFT_THRESHOLD:
            return "large"
        elif size_sqft >= self.config.SMALL_SQFT_THRESHOLD:
            return "midsize"
        else:
            return "small"

    def determine_pue_wue_by_climate_zone(
        self,
        climate_zone,
        efficiency="efficient",
        cooling_configuration=None,
        optimize_for="pue",
        size_sqft=None,
    ):
        """
        Determine typical PUE and WUE values based on IECC climate zone and efficiency level.

        Reads from a CSV data file containing PUE/WUE values keyed by climate zone, cooling
        configuration (case), and quantile. If ``cooling_configuration`` is not provided, the
        best configuration is selected automatically based on ``optimize_for`` and, optionally,
        ``size_sqft``.

        Args:
            climate_zone (str): The IECC climate zone (e.g., "2A", "4B").
            efficiency (str): Either "efficient" (5th percentile) or "inefficient"
                (95th percentile). Defaults to "efficient".
            cooling_configuration (int | None): The cooling configuration number (1-12) to look
                up. If None, the configuration is selected automatically. Valid values::

                    1  - Large-scale DC; Airside economizer + adiabatic cooling
                         + (water-cooled chiller)
                    2  - Large-scale DC; Waterside economizer + (water-cooled chiller)
                    3  - Midsize DC; Airside economizer + (water-cooled chiller)
                    4  - Midsize DC; Waterside economizer + (water-cooled chiller)
                    5  - Midsize DC; Water-cooled chiller
                    6  - Midsize DC; Airside economizer + (air-cooled chiller)
                    7  - Midsize DC; Air-cooled chiller
                    8  - Small DC; Water-cooled chiller
                    9  - Small DC; Air-cooled chiller
                    10 - Small DC; Direct expansion system
                    11 - Liquid-cooled DC; Direct-to-chip liquid loop + dry cooler
                    12 - Liquid-cooled DC; Direct-to-chip liquid loop + water-cooled chiller

            optimize_for (str): When ``cooling_configuration`` is None, selects the
                configuration with the lowest "pue" or lowest "wue". Defaults to "pue".
            size_sqft (float | None): Floor area of the data center in square feet. When
                provided and ``cooling_configuration`` is None, only configurations valid for
                the corresponding size category are considered::

                    Large-scale (> 20,000 sqft): configurations 1, 2, 11, 12
                    Midsize     (1,000-20,000 sqft): configurations 3-7, 11, 12
                    Small       (< 1,000 sqft): configurations 8-10

        Returns:
            tuple: A tuple ``(pue, wue, case_num)`` for the given climate zone,
                cooling configuration, and efficiency level. ``case_num`` is the
                integer cooling-configuration case that was used (either the one
                passed in, or the one selected automatically).
        """

        quantile_map = {"efficient": "5th", "inefficient": "95th"}
        if efficiency not in quantile_map:
            raise ValueError(
                f"efficiency must be 'efficient' or 'inefficient', got '{efficiency}'."
            )
        if optimize_for not in ("pue", "wue"):
            raise ValueError(f"optimize_for must be 'pue' or 'wue', got '{optimize_for}'.")
        quantile = quantile_map[efficiency]

        data_file = Path(__file__).parent / "pue_wue_data" / "pue_wue_data.csv"

        # Load all rows matching climate_zone + quantile
        with data_file.open(newline="") as f:
            matching_rows = [
                (int(row["Case"]), float(row["PUE"]), float(row["WUE"]))
                for row in csv.DictReader(f)
                if row["Climate Zone"] == climate_zone and row["Quantile"] == quantile
            ]

        if not matching_rows:
            raise ValueError(
                f"No PUE/WUE data found for climate zone '{climate_zone}' and efficiency "
                f"'{efficiency}'. Change the climate zone or efficiency level, or supply "
                f"your PUE and WUE values directly."
            )

        if cooling_configuration is not None:
            if cooling_configuration not in self.config.COOLING_CONFIGURATIONS:
                raise ValueError(
                    f"cooling_configuration must be an integer from 1 to 12, "
                    f"got '{cooling_configuration}'."
                )
            for case_num, pue, wue in matching_rows:
                if case_num == cooling_configuration:
                    return (pue, wue, case_num)
            raise ValueError(
                f"No PUE/WUE data found for climate zone '{climate_zone}', "
                f"cooling_configuration {cooling_configuration} "
                f"({self.config.COOLING_CONFIGURATIONS[cooling_configuration]}), and efficiency "
                f"'{efficiency}'. Change the cooling_configuration or efficiency level, or "
                f"supply your PUE and WUE values directly."
            )

        # Filter by size category when size_sqft is provided
        if size_sqft is not None:
            size_category = self._classify_size(size_sqft)
            valid_cases = self.config.SIZE_COOLING_CONFIGURATIONS[size_category]
            matching_rows = [r for r in matching_rows if r[0] in valid_cases]
            if not matching_rows:
                raise ValueError(
                    f"No PUE/WUE data found for climate zone '{climate_zone}', efficiency "
                    f"'{efficiency}', and size category '{size_category}' "
                    f"({size_sqft} sqft). Change the cooling_configuration or size_sqft, "
                    f"or supply your PUE and WUE values directly."
                )

        # Auto-select: pick the row with lowest PUE or lowest WUE
        sort_index = 1 if optimize_for == "pue" else 2
        best = min(matching_rows, key=lambda r: r[sort_index])
        return (best[1], best[2], best[0])


@define(kw_only=True)
class DataCenterPUEWUECostModelConfig(CostModelBaseConfig):
    """
    Configuration class for the DataCenterPUEWUECostModel.

    Attributes:
        electricity_rate (float): Price of electricity in USD/kWh.
        water_rate (float): Price of water in USD/gallon.
        capex_per_mw (float | int): Capital cost per MW of IT equipment capacity in USD/MW.
        fixed_opex_per_mw_per_year (float | int): Fixed annual O&M per MW of IT capacity in
            USD/(MW*year).
    """

    electricity_rate: float = field(validator=validators.ge(0))
    water_rate: float = field(validator=validators.ge(0))
    capex_per_mw: float | int = field(validator=validators.ge(0))
    fixed_opex_per_mw_per_year: float | int = field(validator=validators.ge(0))
    system_capacity_mw: float = field(validator=validators.gt(0))


@register
class DataCenterPUEWUECostModel(CostModelBaseClass):
    """
    Cost model for data centers using PUE and WUE metrics.

    This model calculates costs based on:
    1. Capital costs: capex_per_mw * IT equipment capacity
    2. Fixed operating expenses: fixed_opex_per_mw_per_year * IT equipment capacity
    3. Electricity costs: electricity_rate * total facility energy consumption
    4. Water costs: water_rate * total water consumption

    Inputs from performance model:
        total_facility_power (float array): Total facility power in MW
        water_used (float array): Water consumption in galUS/h

    Cost outputs:
        CapEx: Total capital expenditure in USD
        OpEx: Total operating expenditure over project life in USD
    """

    _time_step_bounds = (
        3600,
        3600,
    )  # (min, max) time step lengths (in seconds) compatible with this model

    def initialize(self):
        super().initialize()
        self.commodity = "compute_load"
        self.commodity_rate_units = "MW"
        self.commodity_amount_units = "MW*h"

    def setup(self):
        self.config = DataCenterPUEWUECostModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost"),
            additional_cls_name=self.__class__.__name__,
        )
        super().setup()
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]

        self.add_input(
            "system_capacity",
            val=self.config.system_capacity_mw,
            units="MW",
            desc="IT equipment rated capacity in MW",
        )

        self.add_input(
            "total_facility_power",
            val=0.0,
            shape=n_timesteps,
            units="MW",
            desc="Total facility power consumption from performance model",
        )

        self.add_input(
            "water_consumed",
            val=0.0,
            shape=n_timesteps,
            units="galUS/h",
            desc="Water consumption from performance model",
        )

        self.add_input(
            "electricity_rate",
            val=self.config.electricity_rate,
            units="USD/kW/h",
            desc="Electricity price",
        )

        self.add_input(
            "water_rate",
            val=self.config.water_rate,
            units="USD/galUS",
            desc="Water price per gallon",
        )

        self.add_input(
            "capex_per_mw",
            val=self.config.capex_per_mw,
            units="USD/MW",
            desc="Capital cost per MW of IT equipment capacity",
        )

        self.add_input(
            "fixed_opex_per_mw_per_year",
            val=self.config.fixed_opex_per_mw_per_year,
            units="USD/(MW*year)",
            desc="Fixed annual O&M per MW of IT capacity",
        )

    def compute(self, inputs, outputs, discrete_inputs=None, discrete_outputs=None):
        """
        Compute capital and operating costs for the data center.

        Operating costs include:
        - Electricity costs: total facility power (kWh) * electricity_rate
        - Water costs: total water used (gallons) * water_rate
        - Fixed O&M: fixed_opex_per_mw_per_year * system_capacity
        """
        system_capacity = inputs["system_capacity"]  # MW of IT equipment
        total_facility_power = inputs["total_facility_power"]  # MW (hourly)
        water_used = inputs["water_consumed"]  # galUS/h
        electricity_rate = inputs["electricity_rate"]  # USD/kWh
        water_rate = inputs["water_rate"]  # USD/galUS
        capex_per_mw = inputs["capex_per_mw"]  # USD/MW
        fixed_opex_per_mw_per_year = inputs["fixed_opex_per_mw_per_year"]  # USD/(MW*year)

        dt = self.options["plant_config"]["plant"]["simulation"]["dt"]

        # Calculate capital expenditure (based on IT equipment capacity)
        capex = capex_per_mw * system_capacity

        # Calculate fixed operating expenses (annual O&M for IT equipment)
        fixed_om = fixed_opex_per_mw_per_year * system_capacity

        # Convert total facility power from MW to kWh
        # total_facility_power is in MW (hourly timesteps)
        # Sum gives MWh for hourly data, multiply by 1000 to get kWh
        total_facility_power_mwh = total_facility_power.sum() * (dt / 3600)
        total_facility_power_kwh = total_facility_power_mwh * 1000

        # Calculate electricity costs
        electricity_cost = total_facility_power_kwh * electricity_rate

        # Convert water used to total gallons consumed
        # water_used is in galUS/h (hourly timesteps)
        # Sum gives galUS for hourly data
        total_water_consumed_gal = water_used.sum() * (dt / 3600)

        # Calculate water costs
        water_cost = total_water_consumed_gal * water_rate

        # Total variable operating expenses (energy and water)
        variable_om = electricity_cost + water_cost

        outputs["CapEx"] = capex
        outputs["OpEx"] = fixed_om
        outputs["VarOpEx"] = variable_om
