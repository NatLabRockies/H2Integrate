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
    """

    system_capacity_mw: float = field(validator=gt_zero)
    compute_electrical_efficiency: float = field(validator=gt_zero)
    cooling_load_ratio: float = field(validator=gte_zero)
    water_use_per_mwh: float = field(validator=gte_zero)


class DataCenterPerformanceModel(PerformanceModelBaseClass):

    def initialize(self):
        super().initialize()
        self.commodity = "compute_load"
        self.commodity_rate_units = "kW"
        self.commodity_amount_units = "kW*h"

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
        Computation for the OM component.

        For a template class this is not implement and raises an error.
        """
        system_capacity = inputs["system_capacity"]  # plant capacity in MW

        # compute load demand, saturated at maximum rated system capacity
        compute_load_demand = np.where(
            inputs["compute_load_demand"] > system_capacity,
            system_capacity,
            inputs["compute_load_demand"],
        )

        electrical_compute_load_demand = (
            compute_load_demand / self.config.compute_electrical_efficiency
        )

        # Total electricity demand is the summation of compute load and cooling load
        total_electricity_demand = (
            electrical_compute_load_demand
            + electrical_compute_load_demand * self.config.cooling_load_ratio
        )

        # available electricity, saturated at maximum rated system capacity
        electricity_available = np.where(
            inputs["electricity_in"] > total_electricity_demand,
            system_capacity,
            inputs["electricity_in"],
        )

        electricity_used = np.minimum.reduce([total_electricity_demand, electricity_available])

        water_used = electrical_compute_load_demand * self.config.water_use_per_mwh

        outputs["unmet_electricity_demand"] = total_electricity_demand - electricity_used
        outputs["water_consumed"] = water_used
        outputs["compute_load_out"] = compute_load_demand


@define(kw_only=True)
class DataCenterCostConfig(CostModelBaseConfig):
    """
    Configuration class for the DataCenterCostModel.
    """

    system_capacity_mw: float = field(validator=gt_zero)
    capex_per_mw: float | int = field(validator=gte_zero)
    fixed_opex_per_mw_per_year: float | int = field(validator=gte_zero)
    variable_opex_per_mwh: float | int = field(validator=gte_zero)


class DataCenterCostModel(CostModelBaseClass):

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
        system_capacity_mw = inputs["system_capacity"]
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
