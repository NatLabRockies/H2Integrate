import numpy as np
from attrs import field, define, validators

from h2integrate.core.utilities import merge_shared_inputs
from h2integrate.core.model_baseclasses import (
    CostModelBaseConfig,
    ResizeablePerformanceModelBaseConfig,
)
from h2integrate.converters.hydrogen.utilities import size_electrolyzer_for_hydrogen_demand
from h2integrate.converters.hydrogen.electrolyzer_baseclass import (
    ElectrolyzerCostBaseClass,
    ElectrolyzerPerformanceBaseClass,
)


@define(kw_only=True)
class HTSEElectrolyzerPerformanceModelConfig(ResizeablePerformanceModelBaseConfig):
    """Configuration class for the HTSE performance model.

    Args:
        n_clusters (int): Number of HTSE clusters in the system.
        nominal_heat_required (float): Nominal thermal energy required per kg of hydrogen
            in kWh/kg.
        nominal_electricity_required (float): Nominal electrical energy required per kg of
            hydrogen in kWh/kg.
        cluster_rating_MW (float): Nameplate electrical rating per cluster in MW.
        uptime_hours_until_eol (int): Hours of operation between replacement events.
            Defaults to ``80000``.
        turndown_ratio (float): Minimum fraction of rated hydrogen production required to
            stay on (unitless). Defaults to ``0.1``.
    """

    n_clusters: int = field(validator=validators.gt(0))
    nominal_heat_required: float = field(validator=validators.gt(0))
    nominal_electricity_required: float = field(validator=validators.gt(0))
    cluster_rating_MW: float = field(validator=validators.gt(0))
    uptime_hours_until_eol: int = field(default=80000, validator=validators.gt(0))
    turndown_ratio: float = field(default=0.1, validator=validators.gt(0))


class HTSEPerformanceModel(ElectrolyzerPerformanceBaseClass):
    """A simplified high-temperature steam electrolysis (HTSE) model.

    This model represents hydrogen production from high-temperature steam electrolysis
    using constant nominal specific energy requirements for electricity and heat. It
    inherits from the electrolyzer base classes, so it is treated as a hydrogen-producing,
    dispatchable technology with an ``electricity_in`` input and a ``hydrogen_out`` output.

    Installed size is inferred from ``n_clusters`` and ``cluster_rating_MW``, and the model
    also supports the ``resize_by_max_feedstock`` (from electricity) and
    ``resize_by_max_commodity`` (from hydrogen) sizing modes inherited from the resizeable
    performance base class. At each timestep the model uses available heat first, supplies
    the remaining required energy electrically when possible, and limits hydrogen
    production by the combined available energy and the turndown threshold. It also exposes
    operating signals useful for coupled systems, including ``heat_demand``,
    ``electricity_demand``, ``electricity_consumed``, and ``water_consumed``.

    In the current implementation, ``electricity_demand`` reports installed electrical
    demand equal to nameplate size, while ``electricity_consumed`` reports timestep
    electricity required by the energy balance.

    The implementation is intentionally simple and should be interpreted as a reduced-order
    plant representation, not a detailed SOEC stack model with thermal transients,
    degradation coupling, startup dynamics, or detailed balance-of-plant behavior.
    """

    def setup(self) -> None:
        self.config = HTSEElectrolyzerPerformanceModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance"),
            strict=False,
            additional_cls_name=self.__class__.__name__,
        )
        super().setup()

        self.add_output(
            "efficiency",
            val=0.0,
            units="unitless",
            desc="Average first-law efficiency based on utilized input energy",
        )
        self.add_output(
            "time_until_replacement",
            val=float(self.config.uptime_hours_until_eol),
            units="h",
            desc="Operating hours until replacement",
        )
        self.add_input(
            "n_clusters",
            val=self.config.n_clusters,
            units="unitless",
            desc="Number of HTSE clusters in the system",
        )
        self.add_input(
            "heat_in",
            val=0.0,
            shape=self.n_timesteps,
            units="kW",
            desc="Thermal energy supplied to the HTSE system",
        )
        self.add_output(
            "electrolyzer_size_mw",
            val=0.0,
            units="MW",
            desc="Installed HTSE nameplate capacity",
        )
        self.add_input("cluster_size", val=1.0, units="MW")
        self.add_input("max_hydrogen_capacity", val=1000.0, units="kg/h")

        self.add_input(
            "water_in",
            val=0.0,
            shape=self.n_timesteps,
            units="galUS/h",
            desc="Water supply",
        )

        self.add_output(
            "water_consumed",
            val=0.0,
            shape=self.n_timesteps,
            units="galUS/h",
            desc="Water consumption",
        )
        self.add_output(
            "heat_demand",
            val=self.config.n_clusters
            * self.config.cluster_rating_MW
            * 1000
            * self.config.nominal_heat_required
            / self.config.nominal_electricity_required,
            shape=self.n_timesteps,
            units="kW",
            desc="Thermal demand by the HTSE system",
        )
        self.add_output(
            "electricity_demand",
            val=0.0,
            shape=self.n_timesteps,
            units="kW",
            desc="Electric demand by the HTSE system",
        )
        self.add_output(
            "electricity_consumed",
            val=0.0,
            shape=self.n_timesteps,
            units="kW",
            desc="Electricity consumed by the HTSE",
        )

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        electrolyzer_size_mw = float(inputs["n_clusters"][0]) * self.config.cluster_rating_MW

        size_mode = discrete_inputs["size_mode"]
        if size_mode != "normal":
            size_flow = discrete_inputs["flow_used_for_sizing"]
            if size_mode == "resize_by_max_feedstock":
                feed_ratio = max(float(inputs["max_feedstock_ratio"][0]), 1.0e-6)
                if size_flow == "electricity":
                    electrolyzer_size_mw = np.max(inputs["electricity_in"]) / 1000.0 * feed_ratio
                else:
                    raise ValueError(f"Cannot resize for '{size_flow}' feedstock")
            elif size_mode == "resize_by_max_commodity":
                comm_ratio = max(float(inputs["max_commodity_ratio"][0]), 1.0e-6)
                if size_flow == "hydrogen":
                    electrolyzer_size_mw = size_electrolyzer_for_hydrogen_demand(
                        float(inputs["max_hydrogen_capacity"][0]) * comm_ratio
                    )
                else:
                    raise ValueError(f"Cannot resize for '{size_flow}' commodity")
            else:
                raise NotImplementedError(f"Sizing mode '{size_mode}' not implemented")

        n_clusters = inputs["n_clusters"]
        electrolyzer_size_mw = n_clusters * self.config.cluster_rating_MW
        electrolyzer_size_kw = electrolyzer_size_mw * 1000.0

        if "system_level_control" in self.options["plant_config"]:
            hydrogen_demand = inputs["hydrogen_command_value"]  # kg/hr?
        else:
            hydrogen_demand = (
                electrolyzer_size_kw / self.config.nominal_electricity_required
            )  # kW/(kWh/kg) = kg/hr
        ratio_heat_elec_nom = (
            self.config.nominal_heat_required / self.config.nominal_electricity_required
        )

        heat_available_kw = inputs["heat_in"]
        electricity_available_kw = inputs["electricity_in"]

        total_specific_energy = (
            self.config.nominal_heat_required + self.config.nominal_electricity_required
        )
        rated_hydrogen_production = electrolyzer_size_kw / self.config.nominal_electricity_required

        # note here that the RATED production is based purely on the electrical requirement.
        # The heat input is a bonus amount. Units here are kg/hr
        heat_demand_kw = hydrogen_demand * self.config.nominal_heat_required

        actual_heat_kw = np.minimum(heat_demand_kw, heat_available_kw)
        electricity_demand_kw = total_specific_energy * hydrogen_demand - actual_heat_kw
        ratio_in = heat_available_kw / electricity_available_kw
        hydrogen_produced = np.where(
            electricity_available_kw < electricity_demand_kw,
            np.where(
                ratio_in > ratio_heat_elec_nom,
                electricity_available_kw / self.config.nominal_electricity_required,
                (heat_available_kw + electricity_available_kw) / total_specific_energy,
            ),
            (actual_heat_kw + electricity_demand_kw) / total_specific_energy,
        )

        actual_heat_kw / ratio_heat_elec_nom

        # in this case, the electricity is insufficient compared to the heat, so we'll use
        # actual_electricity_kw = np.minimum(electricity_demand_kw, electricity_available_kw)
        min_turn_down = self.config.turndown_ratio * rated_hydrogen_production
        hydrogen_produced = np.where(hydrogen_produced >= min_turn_down, hydrogen_produced, 0.0)

        # Density of liquid water at 20°C (293.15 K) and 1 atm (101325 Pa)
        kg_per_liter_water = 1.0
        water_demand_kg_per_h = hydrogen_produced * 18.015 / 2.016
        liters_per_galUS = 3.785411
        water_demand_gal_per_h = (
            water_demand_kg_per_h * (1.0 / kg_per_liter_water) * (1.0 / liters_per_galUS)
        )

        outputs["electricity_consumed"] = electricity_demand_kw
        outputs["hydrogen_out"] = hydrogen_produced
        outputs["heat_demand"] = hydrogen_demand * self.config.nominal_heat_required
        outputs["electricity_demand"] = electrolyzer_size_kw
        outputs["water_consumed"] = water_demand_gal_per_h
        outputs["rated_hydrogen_production"] = rated_hydrogen_production
        outputs["electrolyzer_size_mw"] = electrolyzer_size_mw

        total_hydrogen_produced = np.sum(hydrogen_produced) * (self.dt / 3600.0)
        outputs["total_hydrogen_produced"] = total_hydrogen_produced
        annual_hydrogen = total_hydrogen_produced / self.fraction_of_year_simulated
        outputs["annual_hydrogen_produced"] = np.full(self.plant_life, annual_hydrogen)

        max_production = rated_hydrogen_production * self.n_timesteps * (self.dt / 3600.0)
        capacity_factor = total_hydrogen_produced / max_production if max_production > 0 else 0.0
        outputs["capacity_factor"] = np.full(self.plant_life, capacity_factor)

        utilized_input_kw = actual_heat_kw + electricity_demand_kw
        available_input_kw = heat_available_kw + electricity_available_kw
        with np.errstate(divide="ignore", invalid="ignore"):
            timestep_efficiency = np.divide(
                utilized_input_kw,
                available_input_kw,
                out=np.zeros_like(utilized_input_kw),
                where=available_input_kw > 0,
            )
        outputs["efficiency"] = float(np.mean(timestep_efficiency))

        refurb_schedule = np.zeros(self.plant_life)
        refurb_period = max(1, round(self.config.uptime_hours_until_eol / 8760))
        refurb_schedule[refurb_period : self.plant_life : refurb_period] = 1.0
        outputs["replacement_schedule"] = refurb_schedule
        outputs["time_until_replacement"] = float(self.config.uptime_hours_until_eol)


@define(kw_only=True)
class HTSECostModelConfig(CostModelBaseConfig):
    """Configuration class for the HTSE cost model.

    Args:
        unit_capex (float): Installed capital cost per kW of HTSE electrical size in USD/kW.
        fixed_opex (float, optional): Fixed annual operating cost per kW in USD/(kW*year).
            If omitted, it is populated from ``fixed_capex`` (or ``0.0`` when that is also
            omitted).
        fixed_capex (float, optional): Fallback value used to populate ``fixed_opex`` when
            ``fixed_opex`` is not provided.
        cost_year (int): Dollar year corresponding to the input costs. Defaults to ``2025``.
    """

    unit_capex: float = field(validator=validators.gt(0))
    fixed_opex: float | None = field(default=None)
    fixed_capex: float | None = field(default=None)
    cost_year: int = field(default=2025, converter=int)

    def __attrs_post_init__(self) -> None:
        if self.fixed_opex is None:
            self.fixed_opex = 0.0 if self.fixed_capex is None else float(self.fixed_capex)


class HTSECostModel(ElectrolyzerCostBaseClass):
    """A simple size-based cost model for HTSE.

    The model computes installed capital cost and fixed operating cost from the installed
    HTSE electrical size reported by the performance model:

    - ``CapEx`` from ``unit_capex * electrolyzer_size_kw``
    - ``OpEx`` from ``fixed_opex * electrolyzer_size_kw``

    The current model does not set a nonzero variable operating cost.
    """

    def setup(self) -> None:
        self.config = HTSECostModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost"),
            strict=False,
            additional_cls_name=self.__class__.__name__,
        )
        super().setup()

        self.add_input(
            "electrolyzer_size_mw",
            val=0.0,
            units="MW",
            desc="Installed HTSE nameplate capacity",
        )

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        electrolyzer_size_kw = float(inputs["electrolyzer_size_mw"][0]) * 1000.0
        outputs["CapEx"] = self.config.unit_capex * electrolyzer_size_kw
        outputs["OpEx"] = self.config.fixed_opex * electrolyzer_size_kw
