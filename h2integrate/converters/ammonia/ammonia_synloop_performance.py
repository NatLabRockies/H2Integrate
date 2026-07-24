import numpy as np
from attrs import field, define, validators

from h2integrate.core.dynamics import apply_ramping_limits, startup_loss_multiplier
from h2integrate.core.utilities import merge_shared_inputs
from h2integrate.core.validators import gt_zero, range_val
from h2integrate.tools.constants import H_MW, N_MW, AR_MW
from h2integrate.core.model_baseclasses import (
    ResizeablePerformanceModelBaseClass,
    ResizeablePerformanceModelBaseConfig,
)
from h2integrate.core.commodity_stream_definitions import add_multivariable_output


@define(kw_only=True)
class AmmoniaSynLoopPerformanceConfig(ResizeablePerformanceModelBaseConfig):
    """
    Configuration inputs for the ammonia synthesis loop performance model.

    Attributes marked with a leading asterisk (``*``) are read from
    ``tech_config/ammonia/model_inputs/shared_parameters``; the other inputs come from
    ``tech_config/ammonia/model_inputs/performance_parameters``.

    Attributes:
        size_mode (str): The mode in which the component is sized. Options:

            - "normal": The component size is taken from the tech_config.
            - "resize_by_max_feedstock": Resize based on maximum feedstock availability.
            - "resize_by_max_commodity": Resize based on maximum commodity demand.

        flow_used_for_sizing (str | None): The feedstock/commodity flow used for sizing.
            Required when size_mode is not "normal".
        max_feedstock_ratio (float): Ratio for sizing in "resize_by_max_feedstock" mode.
            Defaults to 1.0.
        max_commodity_ratio (float): Ratio for sizing in "resize_by_max_commodity" mode.
            Defaults to 1.0.
        production_capacity (float): (\\*) The total production capacity of the ammonia synthesis
            loop (in kg ammonia per hour)
        catalyst_consumption_rate (float): (\\*) The mass ratio of catalyst consumed by the reactor
            over its lifetime to ammonia produced (in kg catalyst / kg ammonia)
        catalyst_replacement_interval (float): (\\*) The interval in years when the catalyst is
            replaced
        capacity_factor (float): The ratio of ammonia produced over a year to maximum production
            capacity (as a decimal)
        energy_demand (float): The total energy demand of the ammonia synthesis loop
            (in kWh electricity per kg ammonia).
        heat_output (float): The total heat output of the ammonia synthesis loop
            (in kWh thermal per kg ammonia)
        feed_gas_t (float): The synloop makeup feed gas temperature (in Kelvin)
        feed_gas_p (float): The synloop makeup feed gas pressure (in bar)
        feed_gas_x_n2 (float): The synloop makeup feed gas molar fraction of nitrogen (as a decimal)
        feed_gas_x_h2 (float): The synloop makeup feed gas molar fraction of hydrogen (as a decimal)
        feed_gas_mass_ratio (float): The synloop makeup feed gas mass ratio to ammonia produced (as
            a decimal)
        purge_gas_t (float): The synloop purge gas temperature (in Kelvin)
        purge_gas_p (float): The synloop purge gas pressure (in bar)
        purge_gas_x_n2 (float): The synloop purge gas molar fraction of nitrogen (as a decimal)
        purge_gas_x_h2 (float): The synloop purge gas molar fraction of hydrogen (as a decimal)
        purge_gas_x_ar (float): The synloop purge gas molar fraction of argon (as a decimal)
        purge_gas_x_nh3 (float): The synloop purge gas molar fraction of hydrogen (as a decimal)
        purge_gas_mass_ratio (float): The synloop purge gas mass ratio to ammonia produced (as a
            decimal)
        turndown_ratio (float): The minimum operating point as a fraction of production capacity
            (below this point the ammonia production is zero).
        ramp_up_rate_fraction (float): The maximum hourly increase in production as a fraction of
            production capacity (e.g., 0.1 means production can increase by at most 10% of capacity
            per hour).
        ramp_down_rate_fraction (float): The maximum hourly decrease in production as a fraction of
            production capacity (e.g., 0.1 means production can decrease by at most 10% of capacity
            per hour).
        include_cold_start (bool): Whether to include cold start dynamics.
        off_hours_cold_start (float): The number of hours the plant must be off for a cold start to
            be triggered.
        cold_start_delay_hours (float): The duration of the production delay caused by a cold start
        include_warm_start (bool): Whether to include warm start dynamics.
        off_hours_warm_start (float): The number of hours the plant must be off for a warm start to
            be triggered (should be less than off_hours_cold_start).
        warm_start_delay_hours (float): The duration of the production delay caused by a warm start

    """

    production_capacity: float = field(validator=gt_zero)
    catalyst_consumption_rate: float = field(validator=gt_zero)
    catalyst_replacement_interval: float = field(validator=gt_zero)
    capacity_factor: float = field(validator=range_val(0, 1))
    energy_demand: float = field(validator=gt_zero)
    heat_output: float = field(validator=gt_zero)
    feed_gas_t: float = field(validator=gt_zero)
    feed_gas_p: float = field(validator=gt_zero)
    feed_gas_x_n2: float = field(validator=range_val(0, 1))
    feed_gas_x_h2: float = field(validator=range_val(0, 1))
    feed_gas_mass_ratio: float = field(validator=gt_zero)
    purge_gas_t: float = field(validator=gt_zero)
    purge_gas_p: float = field(validator=gt_zero)
    purge_gas_x_n2: float = field(validator=range_val(0, 1))
    purge_gas_x_h2: float = field(validator=range_val(0, 1))
    purge_gas_x_ar: float = field(validator=range_val(0, 1))
    purge_gas_x_nh3: float = field(validator=range_val(0, 1))
    purge_gas_mass_ratio: float = field(validator=gt_zero)
    # dynamics inputs
    turndown_ratio: float = field(default=0.0, validator=range_val(0.0, 1.0))
    ramp_up_rate_fraction: float = field(default=1.0, validator=range_val(0.0, 1.0))
    ramp_down_rate_fraction: float = field(default=1.0, validator=range_val(0.0, 1.0))

    include_cold_start: bool = field(default=False)
    off_hours_cold_start: float = field(default=None, validator=validators.optional(gt_zero))
    cold_start_delay_hours: float = field(default=None, validator=validators.optional(gt_zero))

    include_warm_start: bool = field(default=False)
    off_hours_warm_start: float = field(default=None, validator=validators.optional(gt_zero))
    warm_start_delay_hours: float = field(default=None, validator=validators.optional(gt_zero))

    def __attrs_post_init__(self):
        super().__attrs_post_init__()

        # If a user has opted into cold- or warm-start dynamics, both required hour
        # values must also be supplied -- the underlying multiplier algorithm has no
        # sensible default for either off-time threshold or the delay duration.
        provided_cold_start_params = all(
            getattr(self, param, None) is not None
            for param in ["off_hours_cold_start", "cold_start_delay_hours"]
        )
        provided_warm_start_params = all(
            getattr(self, param, None) is not None
            for param in ["off_hours_warm_start", "warm_start_delay_hours"]
        )

        # Raise if cold start was enabled but its companion hour values weren't given.
        # The error message lists the params that are still ``None`` so the user knows
        # exactly what to add to their tech config.
        if self.include_cold_start and not provided_cold_start_params:
            missing_params = [
                param
                for param in ["off_hours_cold_start", "cold_start_delay_hours"]
                if getattr(self, param, None) is None
            ]
            raise AttributeError(f"`include_cold_start` is True, missing inputs {missing_params}")

        # Same check for warm start.
        if self.include_warm_start and not provided_warm_start_params:
            missing_params = [
                param
                for param in ["off_hours_warm_start", "warm_start_delay_hours"]
                if getattr(self, param, None) is None
            ]
            raise AttributeError(f"`include_warm_start` is True, missing inputs {missing_params}")


class AmmoniaSynLoopPerformanceModel(ResizeablePerformanceModelBaseClass):
    """
    OpenMDAO component modeling the performance of an ammonia synthesis loop.

    This component calculates the hourly ammonia production based on the available
    hydrogen, nitrogen, and electricity inputs, considering the stoichiometric and
    energetic requirements of the synthesis process. It also computes the unused
    hydrogen, nitrogen, and electricity (as heat), as well as the total ammonia
    produced over the modeled period.

    Purge gas exiting the synthesis loop is exposed as a ``process_gas_mixture``
    multivariable stream with mass flow, hydrogen/nitrogen mass fractions,
    temperature, and pressure. The ``hydrogen_out`` and ``nitrogen_out`` outputs
    represent only unused feedstock (not consumed by the reactor) and no longer
    include the purge gas contribution.

    Attributes:
        config (AmmoniaSynLoopPerformanceConfig): Configuration object containing
            model parameters such as energy demand, nitrogen conversion rate, and
            hydrogen conversion rate.

    Inputs:
        hydrogen_in (array): Hourly hydrogen feed to the synthesis loop [kg/h].
        nitrogen_in (array): Hourly nitrogen feed to the synthesis loop [kg/h].
        electricity_in (array): Hourly electricity supplied to the synthesis loop [MW].

    Outputs:
        ammonia_out (array): Hourly ammonia produced by the synthesis loop [kg/h].
        nitrogen_out (array): Hourly unused nitrogen feedstock (excludes purge gas) [kg/h].
        hydrogen_out (array): Hourly unused hydrogen feedstock (excludes purge gas) [kg/h].
        electricity_out (array): Hourly unused electricity after the synthesis loop [MW].
        heat_out (array): Hourly heat generated by the synthesis loop [MW].
        process_gas_mixture:mass_flow_out (array): Hourly total purge gas mass flow rate [kg/h].
        process_gas_mixture:hydrogen_mass_fraction_out (array): Mass fraction of hydrogen in the
            purge gas [-].
        process_gas_mixture:nitrogen_mass_fraction_out (array): Mass fraction of nitrogen in the
            purge gas  [-].
        process_gas_mixture:argon_mass_fraction_out (array): Mass fraction of argon in the purge
            gas [-].
        process_gas_mixture:ammonia_mass_fraction_out (array): Mass fraction of ammonia in the purge
            gas [-].
        process_gas_mixture:temperature_out (array): Purge gas temperature [K].
        process_gas_mixture:pressure_out (array): Purge gas pressure [bar].
        catalyst_mass (float): Total catalyst mass needed in the synthesis loop [kg].
        total_ammonia_produced (float): Total ammonia produced over the modeled period [kg/year].
        total_hydrogen_consumed (float): Total hydrogen consumed over the modeled period [kg/year].
        total_nitrogen_consumed (float): Total nitrogen consumed over the modeled period [kg/year].
        total_electricity_consumed (float): Total electricity consumed over the modeled
            period [kWh/year].
        limiting_output (array of int): Limiting factor indicator per timestep [-],
            where 0 = nitrogen-limited, 1 = hydrogen-limited, 2 = electricity-limited,
            and 3 = capacity-limited.
        max_hydrogen_capacity (float): Maximum rate of hydrogen consumption  [kg/h].
        ammonia_capacity_factor (float): Ratio of ammonia produced to the maximum production
            capacity [-].

    Notes:
        The ammonia production is limited by the most constraining input (hydrogen,
        nitrogen, or electricity) at each timestep. The component assumes perfect
        conversion efficiency up to the limiting reagent or energy input.
    """

    _time_step_bounds = (
        3600,
        3600,
    )  # (min, max) time step lengths (in seconds) compatible with this model
    _control_classifier = "dispatchable"

    def initialize(self):
        super().initialize()
        self.commodity = "ammonia"
        self.commodity_rate_units = "kg/h"
        self.commodity_amount_units = "kg"

    def setup(self):
        self.config = AmmoniaSynLoopPerformanceConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance"),
            additional_cls_name=self.__class__.__name__,
        )
        super().setup()

        # Capacity inputs
        self.add_input(
            "ammonia_production_capacity", val=self.config.production_capacity, units="kg/h"
        )

        # Flexibility inputs
        self.add_input("turndown_ratio", val=self.config.turndown_ratio, units="unitless")
        self.add_input("ramp_up_rate", val=self.config.ramp_up_rate_fraction, units="unitless")
        self.add_input("ramp_down_rate", val=self.config.ramp_down_rate_fraction, units="unitless")

        if self.config.include_warm_start:
            self.add_input("off_time_warm_start", val=self.config.off_hours_warm_start, units="h")
            self.add_input("warm_start_delay", val=self.config.warm_start_delay_hours, units="h")

        if self.config.include_cold_start:
            self.add_input("off_time_cold_start", val=self.config.off_hours_cold_start, units="h")
            self.add_input("cold_start_delay", val=self.config.cold_start_delay_hours, units="h")

        # Feedstocks input
        self.add_input("hydrogen_in", val=0.0, shape=self.n_timesteps, units="kg/h")
        self.add_input("nitrogen_in", val=0.0, shape=self.n_timesteps, units="kg/h")
        self.add_input("electricity_in", val=0.0, shape=self.n_timesteps, units="kW")

        self.add_output("nitrogen_out", val=0.0, shape=self.n_timesteps, units="kg/h")
        self.add_output("hydrogen_out", val=0.0, shape=self.n_timesteps, units="kg/h")
        self.add_output("electricity_out", val=0.0, shape=self.n_timesteps, units="kW")
        self.add_output("heat_out", val=0.0, shape=self.n_timesteps, units="kW*h/kg")
        self.add_output("catalyst_mass", val=0.0, units="kg")

        # Feedstock consumption profiles
        self.add_output("hydrogen_consumed", val=0.0, shape=self.n_timesteps, units="kg/h")
        self.add_output("electricity_consumed", val=0.0, shape=self.n_timesteps, units="kW")
        self.add_output("nitrogen_consumed", val=0.0, shape=self.n_timesteps, units="kg/h")

        self.add_output("total_hydrogen_consumed", val=0.0, units="kg")
        self.add_output("total_nitrogen_consumed", val=0.0, units="kg")
        self.add_output("total_electricity_consumed", val=0.0, units="kW*h")

        self.add_output("limiting_input", val=0, shape=self.n_timesteps, units="unitless")
        self.add_output("max_hydrogen_capacity", val=1000.0, units="kg/h")

        # Purge gas as a multivariable stream output
        add_multivariable_output(self, "process_gas_mixture", self.n_timesteps)

    def apply_dynamic_operation(self, inputs, nh3_production):
        """Apply ramping constraints and start-up delay losses to the ammonia production profile.

        Calls the model-agnostic helpers in :mod:`h2integrate.core.dynamics`. The
        ammonia-specific work here is just unpacking OpenMDAO inputs into scalar
        production-rate quantities (kg NH3/hr) and combining warm- and cold-start
        multipliers when both are configured.

        Args:
            inputs (dict-like): OM inputs to `compute()` method.
            nh3_production (np.ndarray): pre-constraint ammonia production profile.

        Returns:
            tuple:
                - nh3_production (np.ndarray): production profile after ramping and
                  start-up losses have been applied.
                - consumption_multiplier (np.ndarray): on/off-gated production profile
                  used to scale input-commodity consumption. Feedstocks are consumed during
                  start-up delays (when ammonia output is zeroed) so the consumption
                  multiplier is taken *before* start-up losses are applied.
        """
        rated_capacity = float(inputs["ammonia_production_capacity"][0])

        # raise warning if turndown_ratio is less than zero or greater than 1
        if not (0.0 <= inputs["turndown_ratio"][0] <= 1.0):
            msg = (
                f"Turndown ratio {inputs['turndown_ratio'][0]} is out of bounds. "
                "Clipping to the nearest valid value."
            )
            raise UserWarning(msg)
        # raise warning if ramp_up_rate is less than zero or greater than 1
        if not (0.0 <= inputs["ramp_up_rate"][0] <= 1.0):
            msg = (
                f"Turndown ratio {inputs['ramp_up_rate'][0]} is out of bounds. "
                "Clamping to the nearest valid value."
            )
            raise UserWarning(msg)
        # raise warning if ramp_down_rate is less than zero or greater than 1
        if not (0.0 <= inputs["ramp_down_rate"][0] <= 1.0):
            msg = (
                f"Turndown ratio {inputs['ramp_down_rate'][0]} is out of bounds. "
                "Clamping to the nearest valid value."
            )
            raise UserWarning(msg)

        turndown = float(np.clip(inputs["turndown_ratio"][0], 0.0, 1.0))
        ramp_up_frac = float(np.clip(inputs["ramp_up_rate"][0], 0.0, 1.0))
        ramp_down_frac = float(np.clip(inputs["ramp_down_rate"][0], 0.0, 1.0))

        minimum_production = rated_capacity * turndown
        max_ramp_up_per_hr = rated_capacity * ramp_up_frac
        max_ramp_down_per_hr = rated_capacity * ramp_down_frac

        # Clamp pre-constraint production into the physically allowed range.
        nh3_production = np.clip(nh3_production, a_min=0.0, a_max=rated_capacity)

        # 1. Set production to zero when producing less than the min operating point
        nh3_production = np.where(nh3_production < minimum_production, 0.0, nh3_production)

        # 2. Apply ramping limits on the per-timestep change in production.
        nh3_production = apply_ramping_limits(
            nh3_production,
            dt_seconds=self.dt,
            max_ramp_up_rate=max_ramp_up_per_hr,
            max_ramp_down_rate=max_ramp_down_per_hr,
            commodity_rate_units=self.commodity_rate_units,
            commodity_amount_units=self.commodity_amount_units,
        )

        # 3. Apply start-up delays. When both warm and cold passes are configured we
        # derive each pass's multiplier from the same post-ramping reference profile
        # so that one pass's zeros are not interpreted by the other as new off-events.
        # Each off-block triggers at most one start-up event: if it is long enough to
        # qualify as a cold start, the warm pass is told to ignore it via
        # ``max_offtime_hours``. This avoids double-counting a single physical
        # shutdown when ``warm_start_delay_hours`` would otherwise extend a cold-start
        # event further downstream.
        reference_profile = nh3_production.copy()
        combined_multiplier = np.ones(len(reference_profile))

        cold_offtime_hours = (
            float(inputs["off_time_cold_start"][0]) if "cold_start_delay" in inputs else None
        )

        for offtime_key, delay_key in (
            ("off_time_cold_start", "cold_start_delay"),
            ("off_time_warm_start", "warm_start_delay"),
        ):
            if delay_key not in inputs:
                continue
            # When both warm and cold are enabled, the warm pass excludes off-blocks
            # already claimed by cold. The cold pass always sees every off-block.
            max_offtime = cold_offtime_hours if delay_key == "warm_start_delay" else None
            combined_multiplier *= startup_loss_multiplier(
                reference_profile,
                dt_seconds=self.dt,
                offtime_hours=float(inputs[offtime_key][0]),
                delay_hours=float(inputs[delay_key][0]),
                min_production=minimum_production,
                max_offtime_hours=max_offtime,
            )

        nh3_production = combined_multiplier * nh3_production

        # 4. Reinforce ramping constraints after warm start delays.
        nh3_production = apply_ramping_limits(
            nh3_production,
            dt_seconds=self.dt,
            max_ramp_up_rate=max_ramp_up_per_hr,
            max_ramp_down_rate=max_ramp_down_per_hr,
            commodity_rate_units=self.commodity_rate_units,
            commodity_amount_units=self.commodity_amount_units,
        )

        # 5. Compute the consumption multiplier from the post-dynamic profile.
        # in current behavior the consumption is based on the nh3 produced during
        # that timestep. TODO: develop function to allow for varied consumption based
        # on behavior in that time step (e.g., ramping down uses less n2 and h2 but more power)
        consumption_multiplier = np.where(nh3_production >= minimum_production, nh3_production, 0)

        return nh3_production, consumption_multiplier

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        # Get config values
        nh3_cap = inputs["ammonia_production_capacity"][0]
        cat_consume = self.config.catalyst_consumption_rate  # kg Cat per kg NH3
        cat_replace = self.config.catalyst_replacement_interval  # years
        energy_demand = self.config.energy_demand  # kWh electric per kg NH3
        heat_output = self.config.heat_output  # kWh thermal per kg NH3
        x_h2_feed = self.config.feed_gas_x_h2  # mol frac
        x_n2_feed = self.config.feed_gas_x_n2  # mol frac
        ratio_feed = self.config.feed_gas_mass_ratio  # kg/kg NH3
        x_h2_purge = self.config.purge_gas_x_h2  # mol frac
        x_n2_purge = self.config.purge_gas_x_n2  # mol frac
        ratio_purge = self.config.purge_gas_mass_ratio  # kg/kg NH3

        # Resize if needed
        size_mode = discrete_inputs["size_mode"]
        if size_mode == "normal":
            pass
        elif size_mode == "resize_by_max_feedstock":
            if discrete_inputs["flow_used_for_sizing"] == "hydrogen":
                max_cap_ratio = inputs["max_feedstock_ratio"]
                feed_mw = x_h2_feed * H_MW * 2 + x_n2_feed * N_MW * 2  # g / mol
                w_h2_feed = x_h2_feed * H_MW * 2 / feed_mw  # kg H2 / kg feed gas
                nh3_cap = np.max(inputs["hydrogen_in"]) / (ratio_feed * w_h2_feed) * max_cap_ratio
            else:
                flow = discrete_inputs["flow_used_for_sizing"]
                NotImplementedError(
                    f"The sizing mode '{size_mode}' is not implemented for the '{flow}' flow"
                )
        else:
            NotImplementedError(
                f"The sizing mode '{size_mode}' is not implemented for this converter"
            )

        # Inputs (arrays of length n_timesteps)
        h2_in = inputs["hydrogen_in"]
        n2_in = inputs["nitrogen_in"]
        elec_in = inputs["electricity_in"]

        # Calculate max NH3 production for each input
        feed_mw = x_h2_feed * H_MW * 2 + x_n2_feed * N_MW * 2  # g / mol

        w_h2_feed = x_h2_feed * H_MW * 2 / feed_mw  # kg H2 / kg feed gas
        h2_rate = w_h2_feed * ratio_feed  # kg H2 / kg NH3
        nh3_from_h2 = h2_in / h2_rate  # kg nh3 / hr

        w_n2_feed = x_n2_feed * N_MW * 2 / feed_mw  # kg N2 / kg feed gas
        n2_rate = w_n2_feed * ratio_feed  # kg N2 / kg NH3
        nh3_from_n2 = n2_in / n2_rate  # kg nh3 / hr

        nh3_from_elec = elec_in / energy_demand  # kg nh3 / hr

        # Limiting NH3 production per hour by each input
        nh3_prod = np.minimum.reduce([nh3_from_n2, nh3_from_h2, nh3_from_elec])
        limiters = np.argmin([nh3_from_n2, nh3_from_h2, nh3_from_elec], axis=0)

        # Limiting NH3 production per hour by capacity
        nh3_prod = np.minimum.reduce([nh3_prod, np.full(len(nh3_prod), nh3_cap)])
        cap_lim = 1 - np.argmax([nh3_prod, list(np.full(len(nh3_prod), nh3_cap))], axis=0)

        # Determine what the limiting factor is for each hour
        limiters = np.maximum.reduce([cap_lim * 3, limiters])
        outputs["limiting_input"] = limiters

        # Apply dynamic operation
        nh3_prod, consumption_multiplier = self.apply_dynamic_operation(inputs, nh3_prod)

        # Calculate feedstocks used as consumption_multiplier*feedstock_rate
        used_h2 = consumption_multiplier * h2_rate
        used_n2 = consumption_multiplier * n2_rate
        used_elec = consumption_multiplier * energy_demand  # kW

        # Calculate purge gas composition
        x_ar_purge = self.config.purge_gas_x_ar  # mol frac
        x_nh3_purge = self.config.purge_gas_x_nh3  # mol frac
        purge_mw = (
            x_h2_purge * H_MW * 2
            + x_n2_purge * N_MW * 2
            + x_ar_purge * AR_MW
            + x_nh3_purge * (N_MW + 3 * H_MW)
        )  # g / mol (effective molar mass of purge gas)

        w_h2_purge = x_h2_purge * H_MW * 2 / purge_mw  # kg H2 / kg purge gas
        w_n2_purge = x_n2_purge * N_MW * 2 / purge_mw  # kg N2 / kg purge gas
        w_ar_purge = x_ar_purge * AR_MW / purge_mw  # kg Ar / kg purge gas
        w_nh3_purge = x_nh3_purge * (N_MW + 3 * H_MW) / purge_mw  # kg NH3 / kg purge gas

        # Total purge gas mass flow
        purge_total = ratio_purge * nh3_prod  # kg/h total purge

        # Populate the purge gas multivariable stream (process_gas_mixture)
        outputs["process_gas_mixture:mass_flow_out"] = purge_total
        outputs["process_gas_mixture:hydrogen_mass_fraction_out"] = w_h2_purge
        outputs["process_gas_mixture:nitrogen_mass_fraction_out"] = w_n2_purge
        outputs["process_gas_mixture:argon_mass_fraction_out"] = w_ar_purge
        outputs["process_gas_mixture:ammonia_mass_fraction_out"] = w_nh3_purge
        outputs["process_gas_mixture:temperature_out"] = self.config.purge_gas_t
        outputs["process_gas_mixture:pressure_out"] = self.config.purge_gas_p

        # Calculate catalyst mass
        cat_rate = cat_consume * nh3_prod  # kg Cat / hr
        cat_mass = np.sum(cat_rate) * cat_replace  # kg

        outputs["ammonia_out"] = nh3_prod
        # Unused feedstock only (purge gas now in separate stream)
        outputs["hydrogen_out"] = h2_in - used_h2
        outputs["nitrogen_out"] = n2_in - used_n2
        outputs["electricity_out"] = elec_in - used_elec  # kW
        outputs["heat_out"] = nh3_prod * heat_output
        outputs["catalyst_mass"] = cat_mass
        outputs["total_ammonia_produced"] = max(nh3_prod.sum(), 1e-6) * (self.dt / 3600)

        # Total consumption of feedstocks
        outputs["total_hydrogen_consumed"] = h2_in.sum() * (self.dt / 3600)
        outputs["total_nitrogen_consumed"] = n2_in.sum() * (self.dt / 3600)
        outputs["total_electricity_consumed"] = elec_in.sum() * (self.dt / 3600)  # kW*h

        # Feedstock consumption profiles
        outputs["electricity_consumed"] = used_elec  # kW
        outputs["hydrogen_consumed"] = used_h2  # kg/h
        outputs["nitrogen_consumed"] = used_n2  # kg/h

        h2_cap = nh3_cap * h2_rate  # kg H2 per hour
        outputs["max_hydrogen_capacity"] = h2_cap

        # Calculate capacity factor
        outputs["capacity_factor"] = np.mean(nh3_prod) / nh3_cap

        outputs["rated_ammonia_production"] = nh3_cap
        outputs["annual_ammonia_produced"] = outputs["total_ammonia_produced"] * (
            1 / self.fraction_of_year_simulated
        )
