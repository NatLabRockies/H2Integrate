import numpy as np
from attrs import field, define

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.core.validators import gt_zero, gte_zero
from h2integrate.core.model_baseclasses import (
    CostModelBaseClass,
    CostModelBaseConfig,
    PerformanceModelBaseClass,
)


@define(kw_only=True)
class DataCenterPerformanceConfig(BaseConfig):
    """
    Configuration class for the DataCenterPerformanceModel.

    Attributes:
        system_capacity_mw (float): Maximum compute capacity of the data center in MW.
        compute_electrical_efficiency (float): Efficiency of converting electricity to
            compute load (0 < efficiency <= 1).
        cooling_load_ratio (float): Ratio of cooling load to compute load.
        water_use_per_mwh (float): Water usage per compute load in galUS/MWh.
    """

    system_capacity_mw: float = field(validator=gt_zero)
    compute_electrical_efficiency: float = field(validator=gt_zero)
    cooling_load_ratio: float = field(validator=gte_zero)
    water_use_per_mwh: float = field(validator=gte_zero)


class DataCenterPerformanceModel(PerformanceModelBaseClass):
    """
    Peformance model for data centers.

    This model calculates compute output based on the compute demand and the available
    electricity. The total electricity usage is determined by an overall system electrical
    efficiency as well as an additional cooling load that is proportional to the compute load.
    The amount of water needed for cooling is also computed.

    Inputs:
        system_capacity_mw (float): Maximum compute capacity of the data center in MW.
        compute_electrical_efficiency (float): Efficiency of converting electricity to
            compute load (0 < efficiency <= 1).
        cooling_load_ratio (float): Ratio of cooling load to compute load.
        water_use_per_mwh (float): Water usage per MWh of compute load.
        electricity_in (float array): Electricity input profile in MW/h.
        compute_load_demand (float array): Compute load demand profile in MW.
        water_in (float array): Water input profile in galUS/h.

    Outputs:
        compute_load_out (float array): Actual compute load output in MW.
        unmet_electricity_demand (float array): Unmet electricity demand in MW.
        water_consumed (float array): Water consumed in galUS/h.
    """
    def initialize(self):
        super().initialize()
        self.commodity = "compute_load"
        self.commodity_rate_units = "MW"
        self.commodity_amount_units = "MW*h"

    def setup(self):
        super().setup()
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]
        self.config = DataCenterPerformanceConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance"),
            additional_cls_name=self.__class__.__name__,
        )

        self.add_input(
            f"{self.commodity}_demand",
            val=0.0,
            shape=n_timesteps,
            units=self.commodity_rate_units,
            desc="Data center compute load demand profile",
        )

        self.add_input(
            "electricity_in",
            val=0.0,
            shape=n_timesteps,
            units="MW/h",
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

    def compute(self, inputs, outputs):
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
        system_capacity = self.config.system_capacity_mw  # plant capacity in MW
        # max water consumption in galUS/h
        max_water_consumption = system_capacity * self.config.water_use_per_mwh

        # Compute load demand, saturated at maximum rated system capacity
        compute_load_demand = np.where(
            inputs["compute_load_demand"] > system_capacity,
            system_capacity,
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

        water_demand = electrical_compute_load_demand * self.config.water_use_per_mwh

        # available feedstock, saturated at maximum system feedstock consumption
        water_available = np.where(
            inputs["water_in"] > max_water_consumption,
            max_water_consumption,
            inputs["water_in"],
        )

        water_consumed = np.minimum.reduce([water_demand, water_available])

        outputs["unmet_electricity_demand"] = total_electricity_demand - electricity_used
        outputs["water_consumed"] = water_consumed
        outputs["compute_load_out"] = compute_load_demand


@define(kw_only=True)
class DataCenterCostConfig(CostModelBaseConfig):
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

    system_capacity_mw: float = field(validator=gt_zero)
    capex_per_mw: float | int = field(validator=gte_zero)
    fixed_opex_per_mw_per_year: float | int = field(validator=gte_zero)
    variable_opex_per_mwh: float | int = field(validator=gte_zero)


class DataCenterCostModel(CostModelBaseClass):
    """
    Cost model for data centers.

    This simple cost model calculates capital and operating costs for date centers, including
        costs associated with electricity and water usage.

    Cost components:
    1. Capital costs: capex_per_mw * system_capacity_mw
    2. Fixed operating expenses: fixed_opex_per_mw_per_year * system_capacity_mw
    3. Variable operating expenses: variable_opex_per_mwh * total_compute_load_MWh

    Args:
        CostModelBaseClass (_type_): _description_
    """
    def initialize(self):
        super().initialize()
        self.commodity = "compute_load"
        self.commodity_rate_units = "kW"
        self.commodity_amount_units = "kW*h"

    def setup(self):
        super().setup()
        self.config = DataCenterCostConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost"),
            additional_cls_name=self.__class__.__name__,
        )
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

    def compute(self, inputs, outputs):
        """
        Compute capital and operating costs for the data center.
        """
        system_capacity_mw = inputs["system_capacity_mw"]
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
