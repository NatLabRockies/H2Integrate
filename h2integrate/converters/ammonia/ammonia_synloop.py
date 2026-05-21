import numpy as np
from attrs import field, define, validators
from openmdao.utils import units

from h2integrate.core.utilities import merge_shared_inputs
from h2integrate.core.validators import gt_zero, range_val
from h2integrate.tools.constants import H_MW, N_MW
from h2integrate.core.model_baseclasses import (
    CostModelBaseClass,
    CostModelBaseConfig,
    ResizeablePerformanceModelBaseClass,
    ResizeablePerformanceModelBaseConfig,
)
from h2integrate.tools.inflation.inflate import inflate_cpi, inflate_cepci


@define(kw_only=True)
class AmmoniaSynLoopPerformanceConfig(ResizeablePerformanceModelBaseConfig):
    """
    Configuration inputs for the ammonia synthesis loop performance model.
    *Starred inputs are from tech_config/ammonia/model_inputs/shared_parameters
    The other inputs are from tech_config/ammonia/model_inputs/performance_parameters

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
        *production_capacity (float): The total production capacity of the ammonia synthesis loop
            (in kg ammonia per hour)
        *catalyst_consumption_rate (float): The mass ratio of catalyst consumed by the reactor over
            its lifetime to ammonia produced (in kg catalyst / kg ammonia)
        *catalyst_replacement_interval (float): The interval in years when the catalyst is replaced
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
    off_hours_cold_start: float = field(validator=validators.optional(gt_zero))
    cold_start_delay_hours: float = field(validator=validators.optional(gt_zero))

    include_warm_start: bool = field(default=False)
    off_hours_warm_start: float = field(validator=validators.optional(gt_zero))
    warm_start_delay_hours: float = field(validator=validators.optional(gt_zero))

    def __attrs_post_init__(self):
        super().__attrs_post_init__()

        provided_cold_start_params = all(
            getattr(self, param, None) is not None
            for param in ["off_hours_cold_start", "cold_start_delay_hours"]
        )
        provided_warm_start_params = all(
            getattr(self, param, None) is not None
            for param in ["off_hours_warm_start", "warm_start_delay_hours"]
        )

        if self.include_cold_start and not provided_cold_start_params:
            missing_params = [
                param
                for param in ["off_hours_cold_start", "cold_start_delay_hours"]
                if getattr(self, param, None) is not None
            ]
            raise AttributeError(f"`include_cold_start` is True, missing inputs {missing_params}")

        if self.include_warm_start and not provided_warm_start_params:
            missing_params = [
                param
                for param in ["off_hours_warm_start", "warm_start_delay_hours"]
                if getattr(self, param, None) is not None
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

    Attributes
    ----------
    config : AmmoniaSynLoopPerformanceConfig
        Configuration object containing model parameters such as energy demand,
        nitrogen conversion rate, and hydrogen conversion rate.

    Inputs
    ------
    hydrogen_in : array [kg/h]
        Hourly hydrogen feed to the synthesis loop.
    nitrogen_in : array [kg/h]
        Hourly nitrogen feed to the synthesis loop.
    electricity_in : array [MW]
        Hourly electricity supplied to the synthesis loop.

    Outputs
    -------
    ammonia_out : array [kg/h]
        Hourly ammonia produced by the synthesis loop.
    nitrogen_out : array [kg/h]
        Hourly unused nitrogen after synthesis loop.
    hydrogen_out : array [kg/h]
        Hourly unused hydrogen after synthesis loop.
    electricity_out : array [MW]
        Hourly unused electricity after synthesis loop.
    heat_out : array [MW]
        Hourly heat generated by synthesis loop.
    catalyst_mass: float [kg]
        Total catalyst mass needed in synthesis loop.
    total_ammonia_produced : float [kg/year]
        Total ammonia produced over the modeled period.
    total_hydrogen_consumed : float [kg/year]
        Total hydrogen consumed over the modeled period.
    total_nitrogen_consumed : float [kg/year]
        Total nitrogen consumed over the modeled period.
    total_electricity_consumed : float [kWh/year]
        Total electricity consumed over the modeled period.
    limiting_output: array of ints [-]
        0: nitrogen-limited, 1: hydrogen-limited, 2: electricity-limited 3: capacity-limited
    max_hydrogen_capacity : float [kg/h]
        The maximum rate of hydrogen consumption.
    ammonia_capacity_factor : float [-]
        The ratio of ammonia produced to the maximum production capacity.

    Notes
    -----
    The ammonia production is limited by the most constraining input (hydrogen,
    nitrogen, or electricity) at each timestep. The component assumes perfect
    conversion efficiency up to the limiting reagent or energy input.
    """

    _time_step_bounds = (
        3600,
        3600,
    )  # (min, max) time step lengths (in seconds) compatible with this model

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
        self.add_input("turndown_ratio", val=self.config.turndown_ratio, shape=1, units="unitless")
        self.add_input(
            "ramp_up_rate", val=self.config.ramp_up_rate_fraction, shape=1, units="unitless"
        )
        self.add_input(
            "ramp_down_rate", val=self.config.ramp_down_rate_fraction, shape=1, units="unitless"
        )

        if self.config.include_warm_start:
            self.add_input(
                "off_time_warm_start", val=self.config.off_hours_warm_start, shape=1, units="h"
            )
            self.add_input(
                "warm_start_delay", val=self.config.warm_start_delay_hours, shape=1, units="h"
            )

        if self.config.include_cold_start:
            self.add_input(
                "off_time_cold_start", val=self.config.off_hours_cold_start, shape=1, units="h"
            )
            self.add_input(
                "cold_start_delay", val=self.config.cold_start_delay_hours, shape=1, units="h"
            )

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

    def subdt_offtime_subdt_startup(self, offtime_hrs, start_up_delay_hrs, min_prod_pt, init_prod):
        """Calculates the production multiplier when the off-time to trigger a delayed start-up
        event is less than or equal to the timestep and the start-up delay is also less than
        or equal to the timestep.

        Args:
            offtime_hrs (float): number of "off" hours that triggers a delayed start-up.
                Must be less than or equal to dt.
            start_up_delay_hrs (float): number of hours to go from "off" to "on".
                Must be less than or equal to dt.
            min_prod_pt (float): The minimum production threshold in the same units of init_prod
            init_prod (np.array): The initial production profile.

        Returns:
            np.array: production multiplier to reflect start-up losses.
        """
        # example: offtime of 1, delay of 0.2
        # offtime for start-up delay are less than dt, like electrolyzer model

        # if off-time is less than or equal to dt, then we assume that off-time is equal to dt
        offtime = units.convert_units(offtime_hrs, "h", "s")
        if offtime > self.dt:
            raise ValueError(
                "Please use the method `multidt_offtime_subdt_startup` when"
                " offtime is greater than dt"
            )
        # the logic for this requries the delay to be in seconds
        delay = units.convert_units(start_up_delay_hrs, "h", "s")

        startup_production_multiplier = 1 - (delay / self.dt)

        # on=1, off=0
        on_off_status = np.where(init_prod < min_prod_pt, 0, 1)
        off_indx = np.argwhere(init_prod < min_prod_pt).flatten()

        # no delay at beginning of sim
        # TODO: check that this works if starting off or starting on
        change_status = [0, *list(np.diff(on_off_status))]

        change_status = np.array(change_status)

        prod_multiplier = np.where(change_status > 0, startup_production_multiplier, 1)
        prod_multiplier[off_indx] = 0.0
        return prod_multiplier

    def multidt_offtime_subdt_startup(
        self, offtime_hrs, start_up_delay_hrs, min_prod_pt, init_prod
    ):
        """Calculates the production multiplier when the off-time to trigger a delayed
        start-up event is greater than the timestep and the start-up delay is
        less than or equal to the timestep.

        Args:
            offtime_hrs (float): number of "off" hours that triggers a delayed start-up.
                Must be greater than dt.
            start_up_delay_hrs (float): number of hours to go from "off" to "on".
                Must be less than dt.
            min_prod_pt (float): The minimum production threshold in the same units of init_prod
            init_prod (np.array): The initial production profile.

        Returns:
            np.array: production multiplier to reflect start-up losses.
        """
        # example: offtime of 4, delay of 0.2
        # has to be off for 1 timestep to trigger start-up delay
        # start up takes multiple timesteps

        # the logic for this requires that offtime be converted to the timestep
        # and the delay to be in seconds
        offtime = units.convert_units(offtime_hrs[0], "h", f"{self.dt}*s")
        delay = units.convert_units(start_up_delay_hrs[0], "h", "s")

        # Calculate the production multiplier to represent start-up delay losses
        startup_production_multiplier = 1 - (delay / self.dt)

        # on=1, off=0
        on_off_status = np.where(init_prod < min_prod_pt, 0, 1)
        off_indx = np.argwhere(init_prod < min_prod_pt).flatten()

        # Get the indices of off-events (start and stop)
        off_index_sets = np.ediff1d(np.r_[0, on_off_status == 0, 0]).nonzero()[0].reshape(-1, 2)
        # off_index_sets[:,1] is the end of an off-cycle
        # off_index_sets[:,0] is the start of an off-cycle

        n_dt_off_per_off_event = off_index_sets[:, 1] - off_index_sets[:, 0]

        # Get the indices of off events that are >= the offtime that delays start-up
        index_set_of_off_events = off_index_sets[
            np.argwhere(n_dt_off_per_off_event >= offtime).flatten()
        ]
        # initialize production multiplier as ones
        prod_multiplier = np.ones(len(init_prod))
        # set the multiplier to zero for timesteps where status is off
        prod_multiplier[off_indx] = 0
        # set the multiplier to the startup_production_multiplier in the timestep following
        # an off-event.

        for i in index_set_of_off_events[:, 1]:
            if i == len(init_prod):
                if on_off_status[-1] > startup_production_multiplier:
                    prod_multiplier[-1] = startup_production_multiplier
                continue
            prod_multiplier[i] = startup_production_multiplier

        return prod_multiplier

    def multidt_offtime_multidt_startup(
        self, offtime_hrs, start_up_delay_hrs, min_prod_pt, init_prod
    ):
        """Calculates the production multiplier when the off-time to trigger a delayed
        start-up event is greater than the timestep and the start-up delay is also
        greater than the timestep.

        Args:
            offtime_hrs (float): number of "off" hours that triggers a delayed start-up.
                Must be greater than dt.
            start_up_delay_hrs (float): number of hours to go from "off" to "on".
                Must be greater than dt.
            min_prod_pt (float): The minimum production threshold in the same units of init_prod
            init_prod (np.array): The initial production profile.

        Returns:
            np.array: production multiplier to reflect start-up losses.
        """
        # example: offtime of 4, delay of 5

        # has to be off for multiple timesteps to have some start-up delay
        # start-up delay is also multiple timesteps

        # the logic for this requires that offtime and delay be converted to the timestep
        offtime = units.convert_units(offtime_hrs[0], "h", f"{self.dt}*s")
        delay = units.convert_units(start_up_delay_hrs[0], "h", f"{self.dt}*s")
        full_dt_delay = delay // 1  # number of full timesteps in start-up delay
        partial_dt_delay = delay % 1  # fraction of timestep in start-up delay

        # on=1, off=0
        on_off_status = np.where(init_prod < min_prod_pt, 0, 1)
        off_indx = np.argwhere(init_prod < min_prod_pt).flatten()

        # Get the indices of off-events (start and stop)
        # off_index_sets[:,0] is the index where its turned off
        # off_index_sets[:,1] is the index after its turned on
        off_index_sets = np.ediff1d(np.r_[0, on_off_status == 0, 0]).nonzero()[0].reshape(-1, 2)
        n_dt_off_per_off_event = off_index_sets[:, 1] - off_index_sets[:, 0]

        # Get the indices of off events that are >= the offtime that delays start-up
        # Only look at the off-events that trigger some delayed start-up
        index_set_of_off_events = off_index_sets[
            np.argwhere(n_dt_off_per_off_event >= offtime).flatten()
        ]
        # index_set_of_off_events[:,1] is the first 'on' timestep after the offtime that
        # qualifies a start-up delay

        # initialize production multiplier as ones
        prod_multiplier = np.ones(len(init_prod))
        # set the multiplier to zero for off timesteps
        prod_multiplier[off_indx] = 0

        # Loop through the indices where its turned on after a period
        # of being off that qualifies a start-up delay
        for i_turn_on in index_set_of_off_events[:, 1]:
            if i_turn_on == len(init_prod):
                # TODO: check that this logic is correct
                # when turned on at last timestep
                continue
            # Determine how long until the next shut-off
            on_dt_after_delay_subindx_set = (
                np.ediff1d(np.r_[0, on_off_status[i_turn_on:] == 1, 0])
                .nonzero()[0]
                .reshape(-1, 2)[0]
            )
            # Get the indices from now until the next shutoff
            on_dt_after_delay_indx_set = np.array(
                [int(i_turn_on + ii) for ii in on_dt_after_delay_subindx_set]
            )
            # Determine how long until the next shut-off in dt
            on_dt_after_delay = on_dt_after_delay_indx_set[1] - on_dt_after_delay_indx_set[0]

            # check if we're on long enough before the next shut-off
            if on_dt_after_delay >= delay:
                # time on after the shutoff is greater than the start-up delay
                # start-up delay period ends before next shutoff
                delay_end = int(on_dt_after_delay_indx_set[0] + full_dt_delay)
                # production is zero while starting up
                prod_multiplier[on_dt_after_delay_indx_set[0] : delay_end] = 0

                # apply partial loss for any remaining delay time that is < dt
                if partial_dt_delay > 0:
                    prod_multiplier[delay_end] = 1 - partial_dt_delay

            else:
                # interrupted by another shut-off while starting up
                # TODO: will need to update the amount of off-time for the following start-up (somehow)
                # like if warming up for 2 timesteps then shut off, then we could adjust the
                # off-time for the following on-switch to be 2 timesteps less
                # For now, just set it to zero
                prod_multiplier[on_dt_after_delay_indx_set[0] : on_dt_after_delay_indx_set[1]] = 0

        return prod_multiplier

    def subdt_offtime_multidt_startup(
        self, offtime_hrs, start_up_delay_hrs, min_prod_pt, init_prod
    ):
        """Calculates the production multiplier when the off-time to trigger a delayed
        start-up event is less than or equal to the timestep and the start-up delay is
        greater than the timestep.

        Args:
            offtime_hrs (float): number of "off" hours that triggers a delayed start-up.
                Must be less than or equal to dt.
            start_up_delay_hrs (float): number of hours to go from "off" to "on".
                Must be greater than dt.
            min_prod_pt (float): The minimum production threshold in the same units of init_prod
            init_prod (np.array): The initial production profile.

        Returns:
            np.array: production multiplier to reflect start-up losses.
        """
        # example: offtime of 1, delay of 5
        # has to be off for multiple timesteps to have some start-up delay

        offtime = units.convert_units(offtime_hrs[0], "h", "s")
        if offtime > self.dt:
            raise ValueError("wrong method")

        # logic requires delay to be in number of timesteps
        delay = units.convert_units(start_up_delay_hrs[0], "h", f"{self.dt}*s")
        full_dt_delay = delay // 1
        partial_dt_delay = delay % 1

        on_off_status = np.where(init_prod < min_prod_pt, 0, 1)
        off_indx = np.argwhere(init_prod < min_prod_pt).flatten()

        # initialize production multiplier as ones
        prod_multiplier = np.ones(len(init_prod))
        # set the multiplier to zero for off hours
        prod_multiplier[off_indx] = 0

        # on_index_sets[:,0] is the index where its turned on
        # on_index_sets[:,1] is the index after its turned off
        on_index_sets = np.ediff1d(np.r_[0, on_off_status == 1, 0]).nonzero()[0].reshape(-1, 2)
        n_dt_on_per_on_event = on_index_sets[:, 1] - on_index_sets[:, 0]
        index_set_of_on_events = on_index_sets[
            np.argwhere(n_dt_on_per_on_event >= full_dt_delay).flatten()
        ]

        # looping through the indices of the hours when its turned on
        for i_turn_on in index_set_of_on_events[:, 0]:
            # Determine how long until the next shut-off
            on_dt_after_delay_subindx_set = (
                np.ediff1d(np.r_[0, on_off_status[i_turn_on:] == 1, 0])
                .nonzero()[0]
                .reshape(-1, 2)[0]
            )
            # Get the indices from now until the next shutoff
            on_dt_after_delay_indx_set = np.array(
                [int(i_turn_on + ii) for ii in on_dt_after_delay_subindx_set]
            )

            # Determine how long until the next shut-off in dt
            on_dt_after_delay = on_dt_after_delay_indx_set[1] - on_dt_after_delay_indx_set[0]
            if on_dt_after_delay >= delay:
                # time on after the shutoff is greater than the start-up delay
                # start-up delay period ends before next shutoff
                delay_end = int(on_dt_after_delay_indx_set[0] + full_dt_delay)
                # production is zero while starting up
                prod_multiplier[on_dt_after_delay_indx_set[0] : delay_end] = 0.0
                # apply partial loss for any remaining delay time that is < dt
                if partial_dt_delay > 0:
                    # NOTE this was adjusted to handle fraction of delays, like 4.5 dt delays
                    prod_multiplier[delay_end] = 1 - partial_dt_delay
            else:
                # interrupted by another shut-off while starting up
                # TODO: will need to update the amount of off-time for the following start-up (somehow)
                # like if warming up for 2 hours then shut off, then we could adjust the off-time
                # for the following on-switch to be 2 hrs less
                # For now, just set it to zero
                prod_multiplier[on_dt_after_delay_indx_set[0] : on_dt_after_delay_indx_set[1]] = 0

        return prod_multiplier

    def apply_startup_losses(
        self, offtime_hrs, start_up_delay_hrs, minimum_production, nh3_production
    ):
        """Apply losses for a start-up. A start-up is categorized by the number of timesteps
        that trigger a delayed start-up event (offtime) and the number of timesteps it takes
        to start-up (delay).

        Args:
            offtime_hrs (float): number of "off" hours that triggers a delayed start-up.
                Must be greater than dt.
            start_up_delay_hrs (float): number of hours to go from "off" to "on".
                Must be greater than dt.
            minimum_production (float): The minimum production threshold in the same units of
                ``nh3_production``
            nh3_production (np.ndarray): ammonia production profile prior to start-up delays

        Returns:
            np.ndarray: ammonia production profile with the applied start-up delays and losses
        """
        dt_hrs = self.dt / 3600

        offtime_category = "subdt" if offtime_hrs <= dt_hrs else "multidt"
        startup_category = "subdt" if start_up_delay_hrs <= dt_hrs else "multidt"

        if offtime_category == "subdt" and startup_category == "subdt":
            # off for <=1 dt to cause a start-up delay that is <=1 dt
            production_mult = self.subdt_offtime_subdt_startup(
                offtime_hrs, start_up_delay_hrs, minimum_production, nh3_production
            )
            return production_mult * nh3_production
        if offtime_category == "subdt" and startup_category == "multidt":
            # off for <=1 dt to cause a start-up delay that is > dt
            production_mult = self.subdt_offtime_multidt_startup(
                offtime_hrs, start_up_delay_hrs, minimum_production, nh3_production
            )
            return production_mult * nh3_production
        if offtime_category == "multidt" and startup_category == "subdt":
            # off for > dt to cause a start-up delay that is <= dt
            production_mult = self.multidt_offtime_subdt_startup(
                offtime_hrs, start_up_delay_hrs, minimum_production, nh3_production
            )
            return production_mult * nh3_production
        if offtime_category == "multidt" and startup_category == "multidt":
            # off for > 1 dt to cause a start-up delay that is > dt
            production_mult = self.multidt_offtime_multidt_startup(
                offtime_hrs, start_up_delay_hrs, minimum_production, nh3_production
            )
            return production_mult * nh3_production

    def apply_ramping_constraints(self, init_prod, production_bounds, ramp_rate_bounds):
        # TODO: make this flexible to varying commodity_rate_units and dt
        # TODO: adjust variable naming to not include "demand"
        min_production, rated_production = production_bounds
        ramp_down_rate, ramp_up_rate = ramp_rate_bounds

        # Instantiate the production profile array and populate the first timestep
        # with the first value from pre_demand_met_clipped
        production_profile = np.zeros(len(init_prod))
        production_profile[0] = init_prod[0]

        # Loop through each timestep and adjust for ramping constraints
        for i in range(1, len(production_profile)):
            prior_timestep_demand = production_profile[i - 1]

            # Calculate the change in load from the prior timestep
            load_change = init_prod[i] - prior_timestep_demand

            # If ramp is too steep down, set new_demand accordingly
            if load_change < (-1 * ramp_down_rate):
                new_demand = prior_timestep_demand - ramp_down_rate
                production_profile[i] = np.clip(new_demand, min_production, rated_production)

            # If ramp is too steep up, set new_demand accordingly
            elif load_change > ramp_up_rate:
                new_demand = prior_timestep_demand + ramp_up_rate
                production_profile[i] = np.clip(new_demand, min_production, rated_production)

            else:
                production_profile[i] = init_prod[i]

        return production_profile

    def apply_dynamic_operation(self, inputs, nh3_production):
        """Apply ramping constraints and start-up delay losses to the ammonia production profile.

        Args:
            inputs (om.vectors.default_vector.DefaultVector): OM inputs to `compute()` method
            nh3_production (np.ndarray): array of ammonia production before dynamic
                operation constraints are applied

        Returns:
            2-element tuple containing

            - **nh3_production** (np.ndarray): the ammonia production profile after ramping
                constraints and start-up delay losses have been applied
            - **consumption_multiplier** (np.ndarray): the ammonia production profile to
                calculate input commodity consumption. This is because the input commodities are
                consumed during start-up delays (when no ammonia is being produced)
        """
        # calculate operating constraints in terms of kg NH3/hour
        minimum_production = inputs["ammonia_production_capacity"] * np.clip(
            inputs["turndown_ratio"], a_min=0.0, a_max=1.0
        )
        ramp_up_rate_kg_per_hr = inputs["ammonia_production_capacity"] * np.clip(
            inputs["ramp_up_rate"], a_min=0.0, a_max=1.0
        )
        ramp_down_rate_kg_per_hr = inputs["ammonia_production_capacity"] * np.clip(
            inputs["ramp_down_rate"], a_min=0.0, a_max=1.0
        )

        # Check that the production is positive and less than the rated capacity
        nh3_production = np.clip(
            nh3_production, a_min=0.0, a_max=inputs["ammonia_production_capacity"]
        )

        # 1. first apply ramping constraints, get the nh3_prod

        # apply ramping constraints
        nh3_production = self.apply_ramping_constraints(
            nh3_production,
            (minimum_production[0], inputs["ammonia_production_capacity"][0]),
            (ramp_down_rate_kg_per_hr[0], ramp_up_rate_kg_per_hr[0]),
        )

        # 2. calculate the consumption multiplier as the on_off_status after
        # ramping constraints have been applied multiplied by the production
        # (prior to start-up losses)
        on_off_status = np.where(nh3_production < minimum_production, 0, 1)
        consumption_multiplier = on_off_status * nh3_production

        # NOTE: is there any specific considerations when theres both delays?
        # like should we run cold start first or warm start first
        # ex: should we run always run the multidt_offtime_multidt_delay before
        # running a subdt_offtime_subdt_delay case?

        # 3. apply start-up delays
        if "warm_start_delay" in inputs:
            nh3_production = self.apply_startup_losses(
                inputs["off_time_warm_start"],
                inputs["warm_start_delay"],
                minimum_production,
                nh3_production,
            )

        if "cold_start_delay" in inputs:
            nh3_production = self.apply_startup_losses(
                inputs["off_time_cold_start"],
                inputs["cold_start_delay"],
                minimum_production,
                nh3_production,
            )

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

        # Calculate feedstocks used as consumption_multplier*feedstock_rate
        used_h2 = consumption_multiplier * h2_rate
        used_n2 = consumption_multiplier * n2_rate
        used_elec = consumption_multiplier * energy_demand  # kW

        # Calculate output in purge gas
        purge_mw = x_h2_purge * H_MW * 2 + x_n2_purge * N_MW * 2  # g / mol

        w_h2_purge = x_h2_purge * H_MW * 2 / purge_mw  # kg H2 / kg purge gas
        h2_purge = w_h2_purge * ratio_purge * nh3_prod  # kg H2 / hr

        w_n2_purge = x_n2_purge * N_MW * 2 / purge_mw  # kg N2 / kg purge gas
        n2_purge = w_n2_purge * ratio_purge * nh3_prod  # kg N2 / hr

        # Calculate catalyst mass
        cat_rate = cat_consume * nh3_prod  # kg Cat / hr
        cat_mass = np.sum(cat_rate) * cat_replace  # kg

        outputs["ammonia_out"] = nh3_prod
        outputs["hydrogen_out"] = h2_in - used_h2 + h2_purge
        outputs["nitrogen_out"] = n2_in - used_n2 + n2_purge
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


@define(kw_only=True)
class AmmoniaSynLoopCostConfig(CostModelBaseConfig):
    """
    Configuration inputs for the ammonia synthesis loop cost model.
    *Starred inputs are from tech_config/ammonia/model_inputs/shared_parameters
    The other inputs are from tech_config/ammonia/model_inputs/cost_parameters

    Attributes:
        ---Scaling---
        *production_capacity (float): The total production capacity of the ammonia synthesis loop
            (in kg ammonia per hour)
        baseline_capacity (float): The capacity of the baseline ammonia plant for cost simulations
            (in kg ammonia per hour)
        base_cost_year (int): Year in which base USD costs are derived - to be adjusted using
            CEPCI for capex and CPI for opex.
        capex_scaling_exponent (float): Power applied to ratio of capacities when calculating capex
            from a baseline value at a different capacity.
        labor_scaling_exponent (float): Power applied to ratio of capacities when calculating labor
            cost from a baseline value at a different capacity.

        ---CAPEX---
        asu_capex_base (float): Baseline capital expenditure for the air separation unit [$].
        synloop_capex_base (float): Baseline capital expenditure for the synthesis loop [$].
        heat_capex_base (float) : Baseline capital expenditure for the boiler and steam turbine [$].
        cool_capex_base (float) : Baseline capital expenditure for the cooling tower [$].
        other_eqpt_capex_base (float): Other baseline direct capital expenditures [$].
        land_capex_base (float): Baseline capital expenditure for land to construct the plant [$].
        deprec_noneq_capex_rate (float): Fract of equipment capex for depreciable nonequipment [$].

        ---OPEX---
        labor_rate_base (float) : Baseline all-in labor rate [$/hr].
        num_workers_base (float) : Baseline number of workers for the entire ammonia plant [-].
        hours_yr (float) : Work hours per year per worker [hr/year].
        gen_admin (float) : General and administrative expenses as a fraction of labor [-].
        prop_tax_ins (float) : Property tax and insurance as a fraction of total capex [-].
        maint_rep (float) : Maintenance and repair cost as a fraction of equipment capex [-].
        oxygen_byproduct_rate (float): Rate at which oxygen byproduct is generated [kg O2/kg NH3]
        water_consumption_rate (float): Ratio of cooling water consumed by the reactor [gal/kg NH3]
        *catalyst_consumption_rate (float): The mass ratio of catalyst consumed by the reactor over
            its lifetime to ammonia produced
        *catalyst_replacement_interval (float): The interval in years when the catalyst is replaced
        rebuild_cost_base (float): Cost to rebuild baseline reactor for catalyst replacement [USD].

        ---Feedstock Costs---
        cooling_water_cost_base (float): Cost of cooling water [$/gal H2O]
        catalyst_cost_base (float): Cost of iron-based catalyst [$/kg cat]
        oxygen_price_base (float): Sales price of oxygen co-product [$/kg O2]
    """

    production_capacity: float = field()
    baseline_capacity: float = field()
    base_cost_year: int = field(converter=int)
    capex_scaling_exponent: float = field()
    labor_scaling_exponent: float = field()
    asu_capex_base: float = field()
    synloop_capex_base: float = field()
    heat_capex_base: float = field()
    cool_capex_base: float = field()
    other_eqpt_capex_base: float = field()
    land_capex_base: float = field()
    deprec_noneq_capex_rate: float = field()
    labor_rate_base: float = field()
    num_workers_base: float = field()
    hours_yr: float = field()
    gen_admin: float = field()
    prop_tax_ins: float = field()
    maint_rep: float = field()
    oxygen_byproduct_rate: float = field()
    water_consumption_rate: float = field()
    catalyst_consumption_rate: float = field()
    catalyst_replacement_interval: float = field()
    rebuild_cost_base: float = field()
    cooling_water_cost_base: float = field()
    catalyst_cost_base: float = field()
    oxygen_price_base: float = field()


class AmmoniaSynLoopCostModel(CostModelBaseClass):
    """
    OpenMDAO component modeling the cost of an ammonia synthesis loop.

    This component outputs the capital expenditure (CapEx) and annual operating
    expenditure (OpEx) associated with the synthesis loop, based on provided
    configuration values.

    Attributes
    ----------
    config : AmmoniaSynLoopCostConfig
        Configuration object containing CapEx and annual rebuild cost.

    Inputs
    -------
    total_ammonia_produced : float [kg/year]
        Total ammonia produced over the modeled period.
    total_hydrogen_consumed : float [kg/year]
        Total hydrogen consumed over the modeled period.
    total_nitrogen_consumed : float [kg/year]
        Total nitrogen consumed over the modeled period.
    total_electricity_consumed : float [kg/year]
        Total electricity consumed over the modeled period.

    Outputs
    -------
    CapEx : float [$]
        Capital expenditure for the synthesis loop.
    OpEx : float [$ per year]
        Annual operating expenditure (catalyst replacement/rebuild).
    capex_asu : float [$]
        Capital cost for air separation unit
    capex_synloop : float [$]
        Capital cost for NH3 synthesis loop
    capex_boiler : float [$]
        Capital cost for boilers
    capex_cooling_tower : float [$]
        Capital cost for cooling towers
    capex_direct : float [$]
        Direct capital costs
    capex_depreciable_nonequipment : float [$]
        Depreciable non-equipment capital costs",
    land_cost : float [$]
        Cost of land
    labor_cost : float [$]
        Annual labor cost")
    general_administration_cost : float [$]
        Annual general and administrative cost
    property_tax_insurance : float [$]
        Annual property tax and insurance cost",
    maintenance_cost : float [$]
        Annual maintenance cost
    """

    _time_step_bounds = (
        3600,
        3600,
    )  # (min, max) time step lengths (in seconds) compatible with this model

    def setup(self):
        target_cost_year = self.options["plant_config"]["finance_parameters"][
            "cost_adjustment_parameters"
        ]["target_dollar_year"]
        self.options["tech_config"]["model_inputs"]["cost_parameters"].update(
            {"cost_year": target_cost_year}
        )

        self.config = AmmoniaSynLoopCostConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost"),
            additional_cls_name=self.__class__.__name__,
        )
        super().setup()
        plant_life = int(self.options["plant_config"]["plant"]["plant_life"])

        self.add_input("annual_ammonia_produced", val=0.0, shape=plant_life, units="kg/year")
        self.add_input(
            "rated_ammonia_production", val=self.config.production_capacity, units="kg/h"
        )

        self.add_output(
            "capex_asu", val=0.0, units="USD", desc="Capital cost for air separation unit"
        )
        self.add_output(
            "capex_synloop", val=0.0, units="USD", desc="Capital cost for NH3 synthesis loop"
        )
        self.add_output("capex_boiler", val=0.0, units="USD", desc="Capital cost for boilers")
        self.add_output(
            "capex_cooling_tower", val=0.0, units="USD", desc="Capital cost for cooling towers"
        )
        self.add_output("capex_direct", val=0.0, units="USD", desc="Direct capital costs")
        self.add_output(
            "capex_depreciable_nonequipment",
            val=0.0,
            units="USD",
            desc="Depreciable non-equipment capital costs",
        )
        self.add_output("land_cost", val=0.0, units="USD", desc="Cost of land")

        self.add_output("labor_cost", val=0.0, units="USD/year", desc="Annual labor cost")
        self.add_output(
            "general_administration_cost",
            val=0.0,
            units="USD/year",
            desc="Annual general and administrative cost",
        )
        self.add_output(
            "property_tax_insurance",
            val=0.0,
            units="USD/year",
            desc="Annual property tax and insurance cost",
        )
        self.add_output(
            "maintenance_cost", val=0.0, units="USD/year", desc="Annual maintenance cost"
        )

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        ##---Scaling Ratios---

        # Get config values
        capacity = inputs["rated_ammonia_production"]  # kg NH3 / hr
        base_cap = self.config.baseline_capacity  # kg NH3 / hr
        year = self.options["plant_config"]["finance_parameters"]["cost_adjustment_parameters"][
            "target_dollar_year"
        ]  # dollar year
        base_year = self.config.base_cost_year  # dollar year
        capex_exp = self.config.capex_scaling_exponent  # unitless
        labor_exp = self.config.labor_scaling_exponent  # unitless

        # Get ratios
        cap_ratio = capacity / base_cap
        cepci_ratio = inflate_cepci(1, base_year, year)
        cpi_ratio = inflate_cpi(1, base_year, year)
        capex_ratio = cap_ratio**capex_exp
        labor_ratio = cap_ratio**labor_exp

        ##---CAPEX---

        # Get config values
        asu_capex_base = self.config.asu_capex_base  # USD (base year)
        synloop_capex_base = self.config.synloop_capex_base  # USD (base year)
        heat_capex_base = self.config.heat_capex_base  # USD (base year)
        cool_capex_base = self.config.cool_capex_base  # USD (base year)
        other_eqpt_capex_base = self.config.other_eqpt_capex_base  # USD (base year)
        land_capex_base = self.config.land_capex_base  # USD (base year)
        deprec_noneq_capex_rate = self.config.deprec_noneq_capex_rate  # unitless

        # Apply scaling
        asu_capex = asu_capex_base * capex_ratio * cepci_ratio
        synloop_capex = synloop_capex_base * capex_ratio * cepci_ratio
        heat_capex = heat_capex_base * capex_ratio * cepci_ratio
        cool_capex = cool_capex_base * capex_ratio * cepci_ratio
        other_eqpt_capex = other_eqpt_capex_base * capex_ratio * cepci_ratio
        land_capex = land_capex_base * cap_ratio * cpi_ratio  # Using CPI not CEPCI for land

        # Calculate capex - all in USD
        eqpt_capex = asu_capex + synloop_capex + heat_capex + cool_capex + other_eqpt_capex
        deprec_noneq_capex = land_capex + eqpt_capex * deprec_noneq_capex_rate
        total_capex = eqpt_capex + deprec_noneq_capex

        ##---Fixed OPEX---

        # Get config values
        labor_rate_base = self.config.labor_rate_base  # USD / hr (base year)
        num_workers_base = self.config.num_workers_base  # Workers / plant (base capacity)
        hours_yr = self.config.hours_yr  # hours / year
        gen_admin = self.config.gen_admin  # fraction of labor
        prop_tax_ins = self.config.prop_tax_ins  # fraction of total capex
        maint_rep = self.config.maint_rep  # fraction of equipment capex

        # Apply scaling
        labor_rate = labor_rate_base * cpi_ratio
        num_workers = num_workers_base * labor_ratio

        # Calculate fixed opex - all in USD/year
        labor_opex = labor_rate * num_workers * hours_yr
        gen_admin_opex = labor_opex * gen_admin
        prop_tax_ins_opex = prop_tax_ins * total_capex
        maint_rep_opex = maint_rep * eqpt_capex
        fixed_opex = labor_opex = gen_admin_opex + prop_tax_ins_opex + maint_rep_opex

        ##---Variable OPEX---

        # Get config values
        o2_rate = self.config.oxygen_byproduct_rate  # kg O2 / kg NH3
        h2o_rate = self.config.water_consumption_rate  # kg O2 / kg NH3
        cat_rate = self.config.catalyst_consumption_rate  # kg O2 / kg NH3
        cat_int = self.config.catalyst_replacement_interval  # kg O2 / kg NH3
        rebuild_cost_base = self.config.rebuild_cost_base  # USD
        h2o_cost_base = self.config.cooling_water_cost_base  # USD / kg H2O
        cat_cost_base = self.config.catalyst_cost_base  # USD / kg cat
        o2_price_base = self.config.oxygen_price_base  # USD / kg O2

        # Get total production/consumption
        nh3_prod = inputs["annual_ammonia_produced"].mean()  # kg NH3 /year

        # Apply scaling
        rebuild_cost = rebuild_cost_base * capex_ratio * cepci_ratio
        h2o_cost = h2o_cost_base * cpi_ratio
        cat_cost = cat_cost_base * cpi_ratio
        o2_price = o2_price_base * cpi_ratio

        # Calculate variable opex - all in USD/year
        rebuild_opex = rebuild_cost * cat_int
        cat_opex = cat_cost * cat_rate * nh3_prod
        h2o_opex = h2o_cost * h2o_rate * nh3_prod
        o2_sales = o2_price * o2_rate * nh3_prod
        variable_opex = rebuild_opex + cat_opex + h2o_opex - o2_sales

        ##---Final Outputs---
        outputs["CapEx"] = total_capex
        outputs["OpEx"] = fixed_opex + variable_opex

        outputs["capex_asu"] = asu_capex
        outputs["capex_synloop"] = synloop_capex
        outputs["capex_boiler"] = heat_capex
        outputs["capex_cooling_tower"] = cool_capex
        outputs["capex_direct"] = eqpt_capex
        outputs["capex_depreciable_nonequipment"] = total_capex - eqpt_capex
        outputs["land_cost"] = land_capex

        outputs["labor_cost"] = labor_opex
        outputs["general_administration_cost"] = gen_admin_opex
        outputs["property_tax_insurance"] = prop_tax_ins_opex
        outputs["maintenance_cost"] = maint_rep_opex
