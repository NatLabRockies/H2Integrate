import math
from typing import Any
from datetime import datetime

import numpy as np
import pandas as pd
import pyomo.environ as pyomo
from attrs import field, define, validators
from pyomo.opt import SolverStatus, TerminationCondition

from h2integrate.core.utilities import merge_shared_inputs, build_time_series_from_plant_config
from h2integrate.control.control_strategies.controller_opt_problem_state import DispatchProblemState
from h2integrate.control.control_strategies.pyomo_storage_controller_baseclass import (
    SolverOptions,
    PyomoStorageControllerBaseClass,
    PyomoStorageControllerBaseConfig,
)


@define
class PeakLoadManagementOptimizedStorageControllerConfig(PyomoStorageControllerBaseConfig):
    """Configuration for the Peak Load Management optimized storage controller.

    Inherits base fields from ``PyomoStorageControllerBaseConfig``:
    ``max_capacity``, ``max_soc_fraction``, ``min_soc_fraction``,
    ``init_soc_fraction``, ``n_control_window_hours``, ``commodity``,
    ``commodity_rate_units``, ``tech_name``,
    ``system_commodity_interface_limit``, ``round_digits``.

    Attributes:
        max_charge_rate (float): Maximum charge and discharge rate (kW).
        lmp_signal (list[float]): Locational Marginal Price (LMP)
            forecast time series ($/kWh).
        demand_signal (list[float]): Consumer demand forecast time series (kW).
        peak_window (dict): Hours eligible for dispatch. Keys ``'start'``
            and ``'end'`` must be strings in ``HH:MM:SS`` format.
        GnT_pricingfunction_coeffs (list[float]): Coefficients for G&T pricing function.
            The coefficients of the polynominal function representing the price G&T charges
            the Coop based on the LMP. The list contains the coefficients of the polynomial
            function in decreasing order. (e.g. [1,2] represent 1*x + 2 and [1,2,3] represent
            1*x^2 + 2*x + 3). This function should be a monotonially non-decreasing function.
        performance_incentive (float): Incentive revenue in $/kWh.
            Mutually exclusive with ``performance_incentive_per_event``.
        performance_incentive_per_event (float): Incentive revenue in
            $/event. Converted internally to an effective $/kWh rate using
            ``steps_per_event``, ``dt``, and ``P_max``:
            ``incentive_kWh = incentive_event / (steps_per_event * dt_h * P_max)``.
            Mutually exclusive with ``performance_incentive``.
        charge_efficiency (float): Charge efficiency in [0, 1].
            Defaults to 1.0.
        discharge_efficiency (float): Discharge efficiency in [0, 1].
            Defaults to 1.0.
        n_max_events (int): Maximum discharge events per calendar month.
            Defaults to 10.
        n_control_window_hours (float): Rolling window size in **hours**.
            Converted to an integer timestep count during ``setup()``
            using the simulation ``dt``, so the same value works at any
            resolution. Example: ``10`` at a 30-min ``dt`` gives a
            20-timestep window. Defaults to ``24``.
        signal_threshold_percentile (float): Percentile (0-100) used to
            compute the signal threshold for each rolling window. Only
            timesteps at or above this percentile of the window signal are
            eligible for dispatch. Defaults to 0.0 (all timesteps eligible).
        event_duration (dict): Total dispatch-event duration
            expressed as a ``{units, val}`` dict, where ``units`` is any
            pandas timedelta unit string (e.g. ``'h'``, ``'min'``,
            ``'s'``) and ``val`` is the numeric amount. When set, the
            peak-signal timestep within ``peak_window`` is located and
            every timestep within ``event_duration / 2`` of
            that peak is marked eligible (the window may extend
            beyond the static ``peak_window`` boundaries). When ``None``
            (default) the static ``peak_window`` mask is used unchanged.
            Example: ``{units: 'h', val: 4}`` is +/- 2 h around the daily peak.
        min_peak_separation (dict): Minimum separation between eligible
            peaks, expressed as a ``{units, val}`` dict like
            ``event_duration``. When set, the eligible timesteps identified
            by ``signal_threshold_percentile`` are treated as peaks and
            the first peak is chosen as eligible.
        pyomo_solver (str): Name of the solver used by pyomo to solve the MILP.
            Can be any of ``highs`` or ``glpk``. Default is ``highs``.
        pyomo_solver_options (dict): A dictionary containing options for pyomo solver.
        gt2coop_limit (float): Upper limit of power transferred by G&T to Coop (kW)
        constrain_dispatch_to_set_point (bool): When ``True``, caps
            ``p_discharge``/``p_charge`` each timestep at
            ``{commodity}_set_point - {commodity}_in`` (positive = system
            needs discharge, negative = surplus to absorb),
        control_tier (int): BESS "Exclusive Control" tier (1-4). When set, this layers
            a seasonal on/off-month split on top of the G&T/Co-op dispatch
            above, and the two regimes are always solved as two separate
            MILPs:

            - During Exclusive Control Months, the MILP above still
              applies unchanged (DR incentive maximization) except that
              the monthly cap on discharge is expressed as cycled energy
              (``max_cycles_per_day``) rather than a count of events
              (``n_max_events``), and discharge
              eligibility is evaluated across the whole Exclusive Control
              Month rather than gated to the daily ``peak_window``.
              ``peak_window`` instead doubles as the utility's Class A
              Peak Period: charging is disallowed inside it.
            - Outside Exclusive Control Months the Member has control
              of the BESS, so this controller instead solves a second,
              independent MILP that minimizes the Member's own bill
              (energy + demand/transmission charges) against
              ``demand_signal`` (the Member's own facility load).

            Tiers:

            - ``1``: Exclusive Control all twelve months of the year.
            - ``2``: Exclusive Control during both ``winter_control_months``
              and ``summer_control_months``.
            - ``3``: Exclusive Control during ``summer_control_months`` only.
            - ``4``: Exclusive Control during ``winter_control_months`` only.

            ``n_control_window_hours`` must be chosen so that no rolling
            window straddles an Exclusive Control Month boundary (e.g. a
            window can't contain both late-November and early-December
            timesteps under tier 4) - ``setup()`` raises ``ValueError`` if
            one does, since a single window can only be solved as one of
            the two MILPs above, never a mix of both.
            Defaults to ``None``.
        winter_control_months (list[int]): Calendar months (1-12) making up
            the "Winter Control Months". Defaults to ``[12, 1, 2, 3]``
            (December-March).
        summer_control_months (list[int]): Calendar months (1-12) making up
            the "Summer Control Months". Defaults to ``[6, 7, 8, 9]``
            (June-September).
        max_cycles_per_day (float): During Exclusive Control Months, the
            maximum full-cycle-equivalent energy (relative to
            ``max_capacity * (max_soc_fraction - min_soc_fraction)``) that
            may be discharged per calendar day. Only used when
            ``control_tier`` is set. Defaults to ``1.0`` cycle/day.
        energy_rate (float): Flat energy charge in $/kWh, applied to the
            Member's net metered load (``demand_signal - discharge +
            charge``) during off-months. Required (together with
            ``demand_charge_rate`` and ``demand_charge_window``) whenever
            ``control_tier`` is set, to run the off-month
            bill-minimization problem described above. ``demand_signal``
            doubles as the Member's own facility load for this purpose -
            there is no separate member load profile field, since it is
            the same underlying facility demand either way.
        demand_charge_rate (float): Combined demand + transmission charge
            in $/kW-month, applied once per off-month to that month's
            single highest net load within ``demand_charge_window``.
            Required together with ``energy_rate``.
        demand_charge_window (dict): Time-of-day window, as ``{'start',
            'end'}`` in ``HH:MM:SS`` format, during which the monthly
            demand/transmission peak is determined (e.g.
            ``13:00:00``-``21:00:00`` for "1pm-9pm"). Required together
            with ``energy_rate``.
    """

    max_charge_rate: float = field()
    lmp_signal: list = field()
    demand_signal: list = field()
    peak_window: dict = field()
    GnT_pricingfunction_coeffs: list = field()
    performance_incentive: float = field(default=None)
    performance_incentive_per_event: float = field(default=None)
    charge_efficiency: float = field(validator=(validators.ge(0), validators.le(1)), default=1.0)
    discharge_efficiency: float = field(validator=(validators.ge(0), validators.le(1)), default=1.0)
    n_max_events: int = field(default=10)
    n_control_window_hours: float = field(default=24.0)
    signal_threshold_percentile: float = field(
        default=0.0, validator=(validators.ge(0), validators.le(100))
    )
    event_duration: dict = field(default=None)
    min_peak_separation: dict = field(default=None)
    pyomo_solver: str = field(default="highs")
    pyomo_solver_options: dict = field(default={})
    gt2coop_limit: float = field(default=None)
    constrain_dispatch_to_set_point: bool = field(default=False)
    control_tier: int = field(default=None)
    winter_control_months: list = field(factory=lambda: [12, 1, 2, 3])
    summer_control_months: list = field(factory=lambda: [6, 7, 8, 9])
    max_cycles_per_day: float = field(default=1.0)
    energy_rate: float = field(default=None)
    demand_charge_rate: float = field(default=None)
    demand_charge_window: dict = field(default=None)

    def __attrs_post_init__(self):
        # Make sure n_control_window_hours is an int
        self.n_control_window_hours = math.ceil(self.n_control_window_hours)
        super().__attrs_post_init__()

        both_set = (
            self.performance_incentive is not None
            and self.performance_incentive_per_event is not None
        )
        neither_set = (
            self.performance_incentive is None and self.performance_incentive_per_event is None
        )
        if both_set or neither_set:
            raise ValueError(
                "Exactly one of 'performance_incentive' ($/kWh) or "
                "'performance_incentive_per_event' ($/event) must be set."
            )

        for field_name, value in (
            ("event_duration", self.event_duration),
            ("min_peak_separation", self.min_peak_separation),
        ):
            if value is not None:
                for key in ("units", "val"):
                    if key not in value:
                        raise ValueError(
                            f"{field_name} is missing required key '{key}'. "
                            "Expected dict with 'units' (pandas timedelta unit string) "
                            "and 'val' (int or float)."
                        )
                if not isinstance(value["val"], int | float):
                    raise ValueError(
                        f"{field_name} 'val' must be a numeric value "
                        f"(int or float), got {type(value['val']).__name__}."
                    )

        if self.control_tier is not None and self.control_tier not in (1, 2, 3, 4):
            raise ValueError(f"control_tier must be one of 1, 2, 3, 4; got {self.control_tier!r}.")

        if self.max_cycles_per_day <= 0:
            raise ValueError(f"max_cycles_per_day must be > 0; got {self.max_cycles_per_day!r}.")

        peak_shaving_fields = {
            "energy_rate": self.energy_rate,
            "demand_charge_rate": self.demand_charge_rate,
            "demand_charge_window": self.demand_charge_window,
        }
        n_set = sum(v is not None for v in peak_shaving_fields.values())
        if n_set not in (0, len(peak_shaving_fields)):
            missing = [k for k, v in peak_shaving_fields.items() if v is None]
            raise ValueError(
                "energy_rate, demand_charge_rate, and demand_charge_window must be set "
                f"together; missing: {missing}."
            )
        if self.control_tier is not None and n_set == 0:
            raise ValueError(
                "control_tier requires energy_rate, demand_charge_rate, and "
                "demand_charge_window to be set, to solve the off-month bill-minimization "
                "problem."
            )
        if self.control_tier is None and n_set > 0:
            raise ValueError(
                "energy_rate/demand_charge_rate/demand_charge_window require control_tier "
                "to be set."
            )
        if self.demand_charge_window is not None:
            for key in ("start", "end"):
                if key not in self.demand_charge_window:
                    raise ValueError("demand_charge_window must contain 'start' and 'end' keys")


class PeakLoadManagementOptimizedStorageController(PyomoStorageControllerBaseClass):
    """Demand-response storage controller using a rolling-horizon MILP.

    Each call to the dispatch solver iterates over the full simulation in
    windows of length ``n_control_window_hours``. For each window it builds
    and solves a MILP that maximizes incentive revenue and minimizes Co-Op cost.
    It then passes the resulting dispatch commands to the performance model.
    The terminal SOC of each window is carried forward as the initial SOC of
    the next window.

    Works standalone via ``plant_config["tech_to_dispatch_connections"]`` (as
    in ``examples/34_plm_optimized_dispatch``), or as a storage tech's SLC
    sub-controller with no extra wiring (``examples/35_system_level_control/
    plm_optimized_storage``). Set ``constrain_dispatch_to_set_point=True`` to
    have the SLC's demand signal cap dispatch.

    Setting ``control_tier`` switches on the BESS "Exclusive Control Months"
    seasonal behavior: each rolling window is solved as either the
    Exclusive-Control-Month MILP above or the off-month bill-minimization
    MILP, never a combination of both - ``setup()`` raises ``ValueError`` if
    ``n_control_window_hours`` is such that a window would straddle an
    Exclusive Control Month boundary.
    """

    dr_model: Any
    problem_state: DispatchProblemState
    _time_step_bound = (300, 3600)

    def setup(self):
        """Initialize config, register OpenMDAO inputs, and pre-compute static masks.

        Raises:
            ValueError: If the length of the time series built from
                ``plant_config`` does not match ``n_timesteps``.
        """
        self.config = PeakLoadManagementOptimizedStorageControllerConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "control")
        )

        self.add_input(
            "max_charge_rate",
            val=self.config.max_charge_rate,
            units=self.config.commodity_rate_units,
            desc="Maximum charge/discharge rate P_max",
        )
        self.add_input(
            "storage_capacity",
            val=self.config.max_capacity,
            units=f"{self.config.commodity_rate_units}*h",
            desc="Total storage capacity",
        )

        sim = self.options["plant_config"]["plant"]["simulation"]
        self.n_timesteps = int(sim["n_timesteps"])  # number of "dt"s in the simulation
        self.dt_seconds = int(sim["dt"])  # length of each timestep in seconds

        # n_control_window_hours is stored in hours; convert to timesteps now that dt is known.
        n_cw_steps = max(1, round(self.config.n_control_window_hours * 3600 / self.dt_seconds))
        object.__setattr__(self.config, "n_control_window_hours", n_cw_steps)

        super().setup()

        self.updated_initial_soc = self.config.init_soc_fraction

        self.commodity_info = {
            "commodity_name": self.config.commodity,
            "commodity_storage_units": self.config.commodity_rate_units,
        }

        self.time_index = build_time_series_from_plant_config(
            self.options["plant_config"]
        )  # DatetimeIndex of length n_timesteps

        if len(self.time_index) != self.n_timesteps:
            raise ValueError(
                f"Time series length {len(self.time_index)} != n_timesteps {self.n_timesteps}"
            )

        self.in_peak_window = self._compute_peak_window_mask()  # bool array, shape (T,)
        self.month_ids = self._compute_month_ids()  # int array, shape (T,)

        self.in_exclusive_control_month = self._compute_exclusive_control_mask()
        self.days_in_month_lookup = self._compute_days_in_month_lookup()
        self.in_demand_charge_window = self._compute_demand_charge_window_mask()
        if self.config.control_tier is not None:
            self._check_windows_do_not_span_control_boundary()

        # Computes the number of timesteps in an event based on event_duration and dt_seconds,
        # rounded to nearest int and at least 1.
        if self.config.event_duration is not None:
            self.steps_per_event: int = max(
                1,
                math.ceil(
                    pd.Timedelta(
                        value=self.config.event_duration["val"],
                        unit=self.config.event_duration["units"],
                    ).total_seconds()
                    / self.dt_seconds
                ),
            )
        else:
            self.steps_per_event = 1

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        """Build the DR dispatch solver and write it to discrete outputs.

        Args:
            inputs (dict): OpenMDAO continuous inputs.
            outputs (dict): OpenMDAO continuous outputs.
            discrete_inputs (dict): OpenMDAO discrete inputs.
            discrete_outputs (dict): OpenMDAO discrete outputs. The key
                ``'pyomo_dispatch_solver'`` is set to the callable
                returned by `pyomo_setup`.
        """
        discrete_outputs["pyomo_dispatch_solver"] = self.pyomo_setup(discrete_inputs, inputs)

    def pyomo_setup(self, discrete_inputs, om_inputs):
        """Return the rolling-horizon dispatch solver callable.

        Args:
            discrete_inputs (dict): OpenMDAO discrete inputs.
            om_inputs (dict): OpenMDAO continuous inputs. ``max_charge_rate``
                and ``storage_capacity`` are read from here so that optimizer
                changes to those values are reflected in each solve.

        Returns:
            callable: ``pyomo_dispatch_solver(performance_model,
            performance_model_kwargs, inputs)`` that iterates over the
            simulation in windows of ``n_control_window_hours`` timesteps.
            For each window it:

            1. Builds a fresh MILP from the window's signal slice.
            2. Solves the MILP with a MILP solver
            3. Calls ``performance_model`` with the resulting dispatch
               commands.
            4. Carries the terminal SOC into the next window.

            Returns ``(storage_out, soc_out)`` - two ``np.ndarray`` of
            length ``n_timesteps``.
        """

        P_max = float(om_inputs["max_charge_rate"][0])
        storage_capacity = float(om_inputs["storage_capacity"][0])

        def pyomo_dispatch_solver(
            performance_model,
            performance_model_kwargs,
            inputs,
            commodity_name=self.config.commodity,
        ):
            storage_out = np.zeros(self.n_timesteps)
            soc_out = np.zeros(self.n_timesteps)

            # Per-timestep history of the MILP decision variables, accumulated
            # across all rolling windows. Exposed as attributes so callers
            # (e.g. plotting scripts) can read them via
            # ``model.control_strategies[i].p_discharge_gt_history`` etc.
            # Off-month bill-minimization dispatch (Member-controlled, no G&T
            # interaction) is recorded into the Co-op-side histories.
            self.p_discharge_gt_history = np.zeros(self.n_timesteps)
            self.p_discharge_coop_history = np.zeros(self.n_timesteps)
            self.p_charge_history = np.zeros(self.n_timesteps)
            self.p_tocoop_history = np.zeros(self.n_timesteps)
            self.discharge_gt_bin_history = np.zeros(self.n_timesteps)
            self.discharge_coop_bin_history = np.zeros(self.n_timesteps)
            self.charge_bin_history = np.zeros(self.n_timesteps)

            # Track usage per calendar month so each regime's monthly cap is
            # respected across window boundaries: when
            # control_tier is None, use events per month, when set usecycled energy (kWh).
            events_used_per_month = {}
            energy_used_per_month = {}

            n_w: int = int(self.config.n_control_window_hours)
            # Compute the starting index of each rolling window.
            window_start_indices = list(range(0, self.n_timesteps, n_w))

            # positive = discharge, negative = charge.
            net_demand = (
                inputs[f"{commodity_name}_set_point"] - inputs[f"{commodity_name}_in"]
                if self.config.constrain_dispatch_to_set_point
                else None
            )

            for window_start in window_start_indices:
                window_len: int = min(n_w, self.n_timesteps - window_start)
                month_ids_w = self.month_ids[window_start : window_start + window_len]
                is_exclusive = self.config.control_tier is None or bool(
                    self.in_exclusive_control_month[window_start]
                )
                set_point_w = (
                    net_demand[window_start : window_start + window_len]
                    if net_demand is not None
                    else None
                )

                if is_exclusive:
                    if self.config.control_tier is not None:
                        # Exclusive Control Months: cap is cycled energy (kWh) per
                        # calendar month
                        E_max = storage_capacity * (
                            self.config.max_soc_fraction - self.config.min_soc_fraction
                        )
                        remaining_budget = {
                            int(m): max(
                                0.0,
                                self.config.max_cycles_per_day
                                * self.days_in_month_lookup.get(int(m), 30)
                                * E_max
                                - energy_used_per_month.get(int(m), 0.0),
                            )
                            for m in np.unique(month_ids_w)
                        }
                    else:
                        # Event-based budget
                        remaining_budget = {
                            int(m): max(
                                0,
                                self.config.n_max_events - events_used_per_month.get(int(m), 0),
                            )
                            for m in np.unique(month_ids_w)
                        }

                    # Construct the MILP for this window
                    self.dr_model = self._build_dr_model(
                        window_start=window_start,
                        window_len=window_len,
                        init_soc=self.updated_initial_soc,
                        remaining_budget=remaining_budget,
                        P_max=P_max,
                        storage_capacity=storage_capacity,
                        set_point_w=set_point_w,
                    )
                    self.problem_state = DispatchProblemState()

                    # Solve the optimization problem
                    self.solve_dispatch_model(
                        start_time=window_start,
                        n_days=math.ceil(self.n_timesteps * self.dt_seconds / 86400),
                    )

                    # Track budget usage, and record the per-timestep MILP
                    # decision variables.
                    for t in range(window_len):
                        abs_t = window_start + t

                        d1_val = pyomo.value(self.dr_model.discharge_gt[t])
                        d2_val = pyomo.value(self.dr_model.discharge_coop[t])
                        c_val = pyomo.value(self.dr_model.charge[t])
                        p_d1 = pyomo.value(self.dr_model.p_discharge_gt[t])
                        p_d2 = pyomo.value(self.dr_model.p_discharge_coop[t])

                        self.discharge_gt_bin_history[abs_t] = d1_val
                        self.discharge_coop_bin_history[abs_t] = d2_val
                        self.charge_bin_history[abs_t] = c_val
                        self.p_discharge_gt_history[abs_t] = p_d1
                        self.p_discharge_coop_history[abs_t] = p_d2
                        self.p_charge_history[abs_t] = pyomo.value(self.dr_model.p_charge[t])
                        self.p_tocoop_history[abs_t] = pyomo.value(self.dr_model.p_tocoop[t])

                        if self.config.control_tier is not None:
                            month = int(month_ids_w[t])
                            energy_used_per_month[month] = energy_used_per_month.get(month, 0.0) + (
                                p_d1 + p_d2
                            ) * (self.dt_seconds / 3600.0)
                        else:
                            discharging = d1_val > 0.5
                            prev_discharging = (
                                t > 0 and pyomo.value(self.dr_model.discharge_gt[t - 1]) > 0.5
                            )
                            # Detect the rising edge of a discharge event (0 -> 1)
                            # and count it if it occurs in this window.
                            if discharging and not prev_discharging:
                                month = int(month_ids_w[t])
                                events_used_per_month[month] = (
                                    events_used_per_month.get(month, 0) + 1
                                )
                else:
                    # Off-months: the Member retains control of the DBESS and runs
                    # its own bill-minimization problem instead of dispatching
                    # nothing.
                    self.dr_model = self._build_bill_min_model(
                        window_start=window_start,
                        window_len=window_len,
                        init_soc=self.updated_initial_soc,
                        P_max=P_max,
                        storage_capacity=storage_capacity,
                    )
                    self.problem_state = DispatchProblemState()

                    self.solve_dispatch_model(
                        start_time=window_start,
                        n_days=math.ceil(self.n_timesteps * self.dt_seconds / 86400),
                    )

                    for t in range(window_len):
                        abs_t = window_start + t
                        self.p_discharge_coop_history[abs_t] = pyomo.value(
                            self.dr_model.p_discharge[t]
                        )
                        self.p_charge_history[abs_t] = pyomo.value(self.dr_model.p_charge[t])
                        self.discharge_coop_bin_history[abs_t] = pyomo.value(
                            self.dr_model.discharge[t]
                        )
                        self.charge_bin_history[abs_t] = pyomo.value(self.dr_model.charge[t])

                # Run the performance model for this window.
                storage_out_window, soc_window = performance_model(
                    self._get_storage_dispatch_commands(),
                    **performance_model_kwargs,
                    sim_start_index=window_start,
                )

                # Performance model returns SOC in percent.
                self.updated_initial_soc = np.clip(
                    soc_window[-1] / 100.0,
                    self.config.min_soc_fraction,
                    self.config.max_soc_fraction,
                )

                storage_out[window_start : window_start + window_len] = storage_out_window
                soc_out[window_start : window_start + window_len] = soc_window

            return storage_out, soc_out

        return pyomo_dispatch_solver

    @staticmethod
    def _parse_time_window(window: dict, field_name: str = "peak_window") -> tuple:
        """Parse a ``{'start', 'end'}`` time-of-day config entry into ``datetime.time`` objects.

        Accepts values either as ``HH:MM:SS`` strings or as plain integers
        (seconds since midnight). PyYAML parses unquoted ``HH:MM:SS`` values
        as sexagesimal integers, so both forms are equivalent in YAML.

        Args:
            window (dict): Dict with ``'start'`` and ``'end'`` keys.
            field_name (str): Name used in error messages. Defaults to
                ``'peak_window'``.

        Returns:
            tuple[datetime.time, datetime.time]: ``(start, end)`` times.

        Raises:
            ValueError: If ``'start'`` or ``'end'`` keys are missing, or
                if a value is neither a valid ``HH:MM:SS`` string nor an integer.
        """
        pw = dict(window)
        if "start" not in pw or "end" not in pw:
            raise ValueError(f"{field_name} must contain 'start' and 'end' keys")
        for key in ("start", "end"):
            val = pw[key]
            if isinstance(val, int | float):
                total_seconds = int(val)
                hours, remainder = divmod(total_seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                pw[key] = datetime.min.replace(hour=hours, minute=minutes, second=seconds).time()
            elif isinstance(val, str) and len(val.split(":")) == 3:
                pw[key] = datetime.strptime(val, "%H:%M:%S").time()
            else:
                raise ValueError(
                    f"{field_name} '{key}' must be HH:MM:SS string or integer seconds, got {val!r}."
                )
        return pw["start"], pw["end"]

    def _parse_peak_window(self) -> tuple:
        """Parse the ``peak_window`` config entry into ``datetime.time`` objects.

        Returns:
            tuple[datetime.time, datetime.time]: ``(start, end)`` times.

        Raises:
            ValueError: If ``'start'`` or ``'end'`` keys are missing, or
                if a value is neither a valid ``HH:MM:SS`` string nor an integer.
        """
        return self._parse_time_window(self.config.peak_window, "peak_window")

    def _compute_time_mask(self, start, end) -> np.ndarray:
        """Build a boolean mask that is ``True`` for timesteps inside ``[start, end)``.

        Args:
            start (datetime.time): Window start (inclusive).
            end (datetime.time): Window end (exclusive).

        Returns:
            np.ndarray: Boolean array of shape ``(n_timesteps,)``.

        Raises:
            ValueError: If ``end`` is before ``start``.
        """
        times = pd.DatetimeIndex(self.time_index).time
        if end < start:
            raise ValueError("window end time must be after start time.")
        return np.array([start <= t < end for t in times])

    def _compute_peak_window_mask(self) -> np.ndarray:
        """Build a boolean mask that is ``True`` for timesteps inside the peak window.

        Returns:
            np.ndarray: Boolean array of shape ``(n_timesteps,)``.

        Raises:
            ValueError: If ``peak_window`` end time is before start time.
        """
        start, end = self._parse_peak_window()
        return self._compute_time_mask(start, end)

    def _compute_month_ids(self) -> np.ndarray:
        """Return the calendar month index (1-12) for each timestep.

        Returns:
            np.ndarray: Integer array of shape ``(n_timesteps,)``.
        """
        return pd.DatetimeIndex(self.time_index).month.to_numpy()

    def _compute_exclusive_control_mask(self) -> np.ndarray:
        """Build a boolean mask that is ``True`` for timesteps in an Exclusive Control Month.

        The set of Exclusive Control Months is determined by ``control_tier``:
        Tier 1 is all twelve months; Tier 2 is ``winter_control_months`` union
        ``summer_control_months``; Tier 3 is ``summer_control_months`` only;
        Tier 4 is ``winter_control_months`` only.

        Returns:
            np.ndarray: Boolean array of shape ``(n_timesteps,)``. All
            ``False`` when ``control_tier`` is ``None``.
        """
        if self.config.control_tier is None:
            return np.zeros(len(self.month_ids), dtype=bool)

        winter = set(self.config.winter_control_months)
        summer = set(self.config.summer_control_months)
        tier_months = {
            1: set(range(1, 13)),
            2: winter | summer,
            3: summer,
            4: winter,
        }
        months = tier_months[self.config.control_tier]
        return np.isin(self.month_ids, sorted(months))

    def _compute_demand_charge_window_mask(self) -> np.ndarray:
        """Build a boolean mask that is ``True`` during the demand-charge window.

        This is the time-of-day window (e.g. "1pm-9pm") used to determine
        each off-month's demand/transmission-charge-setting peak.

        Returns:
            np.ndarray: Boolean array of shape ``(n_timesteps,)``. All
            ``False`` when ``demand_charge_window`` is ``None``.
        """
        if self.config.demand_charge_window is None:
            return np.zeros(len(self.month_ids), dtype=bool)
        start, end = self._parse_time_window(
            self.config.demand_charge_window, "demand_charge_window"
        )
        return self._compute_time_mask(start, end)

    def _compute_days_in_month_lookup(self) -> dict:
        """Map each calendar month present in the simulation to its day count.

        For simulations spanning multiple years, the day count is taken
        from the first occurrence of that calendar month (matching the
        existing ``month_ids`` simplification of not tracking year).

        Returns:
            dict[int, int]: Mapping of month (1-12) to number of days.
        """
        idx = pd.DatetimeIndex(self.time_index)
        lookup = {}
        for month in range(1, 13):
            matches = idx[idx.month == month]
            if len(matches) == 0:
                continue
            lookup[month] = int(
                pd.Timestamp(year=matches[0].year, month=month, day=1).days_in_month
            )
        return lookup

    def _check_windows_do_not_span_control_boundary(self) -> None:
        """Raise if any rolling window mixes Exclusive Control and off-month timesteps.

        The Exclusive Control Month MILP (``_build_dr_model``) and the
        off-month bill-minimization MILP (``_build_bill_min_model``) are two
        different optimization problems; a single rolling window must not have both
        objectives.

        Raises:
            ValueError: If a rolling window contains both Exclusive Control
                and off-month timesteps.
        """
        n_w = int(self.config.n_control_window_hours)
        for window_start in range(0, self.n_timesteps, n_w):
            window_len = min(n_w, self.n_timesteps - window_start)
            status = self.in_exclusive_control_month[window_start : window_start + window_len]
            if status.any() and not status.all():
                raise ValueError(
                    "Rolling window starting at timestep "
                    f"{window_start} (length {window_len}) spans an Exclusive "
                    "Control Month boundary, mixing Exclusive Control and "
                    "off-month timesteps within a single window. Choose "
                    "n_control_window_hours so that rolling windows align with "
                    "Exclusive Control Month boundaries."
                )

    def _compute_eligible_mask(
        self,
        signal_window: np.ndarray,
        dispatch_mask: np.ndarray | None = None,
    ) -> np.ndarray:
        """Build a boolean mask for timesteps whose signal meets the dispatch threshold.

        The threshold percentile is computed from ``signal_window`` values
        that fall inside ``dispatch_mask`` (i.e. the current dispatch
        window).
        When ``dispatch_mask`` is ``None`` the full ``signal_window`` is
        used. When ``signal_threshold_percentile`` is 0.0 all timesteps
        are eligible.
        If there are multiple timesteps above the threshold within a window and
        ``min_peak_separation`` is set, only the first one is eligible.

        Args:
            signal_window (np.ndarray): Signal values for the current
                rolling window.
            dispatch_mask (np.ndarray | None): Boolean mask of shape
                ``(len(signal_window),)`` indicating which timesteps
                belong to the current dispatch window. Defaults to
                ``None`` (use full window).

        Returns:
            np.ndarray: Boolean array of shape ``(len(signal_window),)``.
                ``True`` where ``signal_t >= threshold``.
        """
        # Use all the timesteps in the window if no dispatch_mask is provided, otherwise restrict
        # to the dispatch window
        mask = (
            dispatch_mask if dispatch_mask is not None else np.ones(len(signal_window), dtype=bool)
        )

        # If the threshold percentile is 0 or there are dispatch_window is all 0s
        # all timesteps are eligible
        if self.config.signal_threshold_percentile == 0.0 or not mask.any():
            return mask.copy()

        # Keep only the timesteps where the signal is above the threshold computed from the
        # dispatch window
        threshold = np.percentile(signal_window[mask], self.config.signal_threshold_percentile)
        eligible = mask & (signal_window >= threshold)

        if self.config.min_peak_separation is not None:
            sep_steps = math.ceil(
                pd.Timedelta(
                    value=self.config.min_peak_separation["val"],
                    unit=self.config.min_peak_separation["units"],
                ).total_seconds()
                / self.dt_seconds
            )
            # Keep the first peak; drop any subsequent peaks
            # within sep_steps of the last kept one.
            # This is a greedy choice but subsequent iterations will
            # use a smarter logic
            kept = []
            for idx in np.where(eligible)[0]:
                if not kept or int(idx) - kept[-1] >= sep_steps:
                    # Won't enter this condition if the peaks are too close together
                    kept.append(int(idx))
            eligible = np.zeros(len(signal_window), dtype=bool)
            eligible[kept] = True

        return eligible

    def _compute_event_window_mask(
        self,
        eligible_mask: np.ndarray,
    ) -> np.ndarray:
        """Expand each eligible peak timestep by +/- event_duration/2.

        Every True timestep in ``eligible_mask`` is
        treated as a peak and all timesteps within ``event_duration / 2``
        of it are marked eligible. When ``event_duration`` is ``None``
        returns ``eligible_mask`` unchanged.

        Args:
            eligible_mask (np.ndarray): Boolean mask of peak timesteps,
                shape ``(window_len,)``.

        Returns:
            np.ndarray: Boolean mask of shape ``(window_len,)``.
        """
        if self.config.event_duration is None:
            return eligible_mask.copy()

        half_event_steps = self.steps_per_event / 2
        peak_indices = np.where(eligible_mask)[0]
        event_mask = np.zeros(len(eligible_mask), dtype=bool)
        for peak in peak_indices:
            near_peak = np.abs(np.arange(len(eligible_mask)) - peak) <= half_event_steps
            event_mask |= near_peak
        return event_mask

    def _build_dr_model(
        self,
        window_start: int,
        window_len: int,
        init_soc: float,
        remaining_budget: dict,
        P_max: float,
        storage_capacity: float,
        set_point_w: np.ndarray | None = None,
    ) -> pyomo.ConcreteModel:
        """Build the DR MILP for a single rolling window.

        Decision variables
        ------------------
        discharge_gt[t] : binary
            Event indicator — 1 if a discharge event due to G&T is active at timestep t.
            Used for event counting and window feasibility constraints only.
        discharge_coop[t] : binary
            Event indicator — 1 if a discharge event due to Coop is active at timestep t.
            Used for event counting and window feasibility constraints only.
        charge[t] : binary
            Event indicator — 1 if a charge event is active at timestep t.
        p_discharge_gt[t] : continuous in [0, P_max]
            Actual discharge power (kW) due to G&T. Linked to the binary via the
            McCormick upper-bound constraint ``p_discharge_gt[t] <= P_max * discharge_gt[t]``.
        p_discharge_coop[t] : continuous in [0, P_max]
            Actual discharge power (kW) due to Coop. Linked to the binary via the
            McCormick upper-bound constraint ``p_discharge_coop[t] <= P_max * discharge_coop[t]``.
        p_charge[t] : continuous in [0, P_max]
            Actual charge power (kW). Linked via ``p_charge[t] <= P_max * charge[t]``.
        p_tocoop[t]: continuous
            Power supplied (kW) by G&T to Coop
        soc[t] : continuous in [soc_min, soc_max]
            State of charge (fraction).

        Args:
            window_start (int): Timestep index of the first timestep
                in this window.
            window_len (int): Number of timesteps in this window.
            init_soc (float): State-of-charge fraction at the start of
                this window.
            remaining_budget (dict): Mapping of ``month_id (int)`` to the
                remaining monthly budget for that month, computed by
                subtracting usage already dispatched in earlier windows.
                When ``control_tier`` is ``None`` this is a count of
                remaining event slots (``n_max_events`` minus events used).
                When ``control_tier`` is set it is instead a remaining
                energy budget in kWh (``max_cycles_per_day *
                days_in_month * E_max`` minus energy already discharged
                that month).
            P_max (float): Maximum charge/discharge rate (kW), taken
                from OpenMDAO inputs so optimizer changes are reflected.
            storage_capacity (float): Total storage capacity (kWh), taken
                from OpenMDAO inputs so optimizer changes are reflected.
            set_point_w (np.ndarray | None): Per-timestep net-demand slice
                (already netted by the caller), or ``None`` when
                ``config.constrain_dispatch_to_set_point`` is ``False``.
                When provided, caps ``p_discharge``/``p_charge`` at its
                magnitude each timestep.

        Returns:
            pyomo.ConcreteModel: Fully formed MILP ready to solve.
        """
        m: Any = pyomo.ConcreteModel(name="plm_dr")

        eta_c = self.config.charge_efficiency
        eta_d = self.config.discharge_efficiency
        soc_max = self.config.max_soc_fraction
        soc_min = self.config.min_soc_fraction
        dt_hours = self.dt_seconds / 3600.0

        # This  converts the incentive from $/event to an effective $/kWh
        # rate based on the number of timesteps in an event (steps_per_event),
        #  the length of each timestep in hours (dt_hours), and the max power (P_max).
        if self.config.performance_incentive_per_event is not None:
            incentive = self.config.performance_incentive_per_event / (
                self.steps_per_event * dt_hours * P_max
            )
        else:
            incentive = self.config.performance_incentive
        N_max = self.config.n_max_events

        # Only the timesteps within the current window are relevant
        w = slice(window_start, window_start + window_len)
        in_peak_window_w = self.in_peak_window[w]
        month_ids_w = self.month_ids[w]
        signal_w = np.asarray(self.config.lmp_signal, dtype=float)[w]
        signal_d = np.asarray(self.config.demand_signal, dtype=float)[w]

        control_tier = self.config.control_tier
        if control_tier is not None:
            # Exclusive Control Months:
            # Use percentage threshold to determine eligible timesteps for discharge.
            # Charging is disallowed during the peak window.
            eligible_t_w = self._compute_eligible_mask(signal_w, None)
            dispatch_window_w = eligible_t_w
            charge_restricted_w = in_peak_window_w
        else:
            # Eligible timesteps for discharge based on percentile
            eligible_t_w = self._compute_eligible_mask(signal_w, in_peak_window_w)
            # Expand eligible timesteps into event windows based on event_duration
            dispatch_window_w = self._compute_event_window_mask(eligible_t_w)
            eligible_t_w = dispatch_window_w
            charge_restricted_w = dispatch_window_w

        months_in_window = np.unique(month_ids_w).tolist()

        # Sets we need to iterate on in the constraints and objective
        m.T = pyomo.Set(initialize=range(window_len), doc="Timesteps in window")
        m.M = pyomo.Set(initialize=months_in_window, doc="Months in window")

        ## Decision Variables
        # Binary event indicators- used for event counting and window constraints.
        m.discharge_gt = pyomo.Var(
            m.T, domain=pyomo.Binary, doc="1 if a discharge to G&T event is active at timestep t"
        )
        m.discharge_coop = pyomo.Var(
            m.T, domain=pyomo.Binary, doc="1 if a discharge Co-Op event is active at timestep t"
        )
        m.charge = pyomo.Var(
            m.T, domain=pyomo.Binary, doc="1 if a charge event is active at timestep t"
        )
        # Actual kW dispatched each timestep.
        m.p_discharge_gt = pyomo.Var(
            m.T,
            domain=pyomo.NonNegativeReals,
            bounds=(0, P_max),
            doc="Discharge power (kW) due to G&T at timestep t",
        )
        m.p_discharge_coop = pyomo.Var(
            m.T,
            domain=pyomo.NonNegativeReals,
            bounds=(0, P_max),
            doc="Discharge power due to Co-Op (kW) at timestep t",
        )
        m.p_charge = pyomo.Var(
            m.T,
            domain=pyomo.NonNegativeReals,
            bounds=(0, P_max),
            doc="Charge power (kW) at timestep t",
        )
        # Battery SOC
        m.soc = pyomo.Var(
            m.T,
            domain=pyomo.NonNegativeReals,
            bounds=(soc_min, soc_max),
            doc="State of charge SoC_t",
        )

        # Power transmitted to Coop
        m.p_tocoop = pyomo.Var(
            m.T,
            domain=pyomo.NonNegativeReals,
            bounds=(0, self.config.gt2coop_limit),
            doc="Power supplied by G&T to Co-Op (kW)",
        )

        # Objective is maximizing incentive revenue is earned for every kWh discharged and
        # minimizing the cost of energy for the Coop.
        m.objective = pyomo.Objective(
            expr=-incentive * dt_hours * sum(m.p_discharge_gt[t] for t in m.T)
            + dt_hours * sum(self._GnT_pricingfunction(signal_w[t]) * m.p_tocoop[t] for t in m.T),
            sense=pyomo.minimize,
        )

        ## Constraints
        # Discharge can only occur during the dispatch window.
        m.peak_window_only = pyomo.Constraint(
            m.T,
            rule=lambda mdl, t: (
                mdl.discharge_gt[t] == 0 if not dispatch_window_w[t] else pyomo.Constraint.Skip
            ),
        )

        # Discharge can only occur at eligible timesteps.
        m.high_signal_only = pyomo.Constraint(
            m.T,
            rule=lambda mdl, t: mdl.discharge_gt[t] <= int(eligible_t_w[t]),
        )

        if control_tier is not None:
            # Exclusive Control Months: the cap is on cycled energy (kWh) per calendar
            # month, not on discrete events - "total Cycles in
            # each month cannot exceed the equivalent of one Cycle per calendar day".
            E_max = storage_capacity * (soc_max - soc_min)

            def monthly_cycle_cap_rule(mdl, month):
                ts_in_month = [t for t in mdl.T if month_ids_w[t] == month]
                if not ts_in_month:
                    return pyomo.Constraint.Skip
                default_budget_kwh = (
                    self.config.max_cycles_per_day
                    * self.days_in_month_lookup.get(month, 30)
                    * E_max
                )
                budget_kwh = (
                    remaining_budget[month] if month in remaining_budget else default_budget_kwh
                )
                return (
                    sum(mdl.p_discharge_gt[t] + mdl.p_discharge_coop[t] for t in ts_in_month)
                    * dt_hours
                    <= budget_kwh
                )

            m.max_events = pyomo.Constraint(m.M, rule=monthly_cycle_cap_rule)
        else:
            # There is a limit on the number of events, not discharge timesteps.
            # However, we know the number of timesteps in the event from steps_per_event,
            # so we can indirectly limit the number of discharge timesteps in each month
            # by multiplying the event cap by steps_per_event.
            def max_events_rule(mdl, month):
                ts_in_month = [t for t in mdl.T if month_ids_w[t] == month]
                if not ts_in_month:
                    return pyomo.Constraint.Skip
                budget_steps = (
                    remaining_budget[month] if month in remaining_budget else N_max
                ) * self.steps_per_event
                return sum(mdl.discharge_gt[t] for t in ts_in_month) <= budget_steps

            m.max_events = pyomo.Constraint(m.M, rule=max_events_rule)

        # Power is zero when the binary is 0, and at most P_max when 1.
        m.discharge_gt_power_link = pyomo.Constraint(
            m.T,
            rule=lambda mdl, t: mdl.p_discharge_gt[t] <= P_max * mdl.discharge_gt[t],
        )
        m.discharge_coop_power_link = pyomo.Constraint(
            m.T,
            rule=lambda mdl, t: mdl.p_discharge_coop[t] <= P_max * mdl.discharge_coop[t],
        )
        m.charge_power_link = pyomo.Constraint(
            m.T,
            rule=lambda mdl, t: mdl.p_charge[t] <= P_max * mdl.charge[t],
        )

        if set_point_w is not None:
            # Cap dispatch at what the system actually needs/can absorb this timestep.
            m.discharge_set_point_cap_gt = pyomo.Constraint(
                m.T,
                rule=lambda mdl, t: mdl.p_discharge_gt[t] <= max(float(set_point_w[t]), 0.0),
            )
            m.discharge_set_point_cap_coop = pyomo.Constraint(
                m.T,
                rule=lambda mdl, t: mdl.p_discharge_coop[t] <= max(float(set_point_w[t]), 0.0),
            )
            m.charge_set_point_cap = pyomo.Constraint(
                m.T,
                rule=lambda mdl, t: mdl.p_charge[t] <= max(-float(set_point_w[t]), 0.0),
            )

        m.soc_init = pyomo.Constraint(expr=m.soc[0] == init_soc)

        # Dynamics of the battery SOC evolution.
        def soc_evolution_rule(mdl, t):
            if t == 0:
                return mdl.soc[t] == (
                    init_soc
                    + eta_c * mdl.p_charge[t] * dt_hours / storage_capacity
                    - mdl.p_discharge_gt[t] * dt_hours / (eta_d * storage_capacity)
                    - mdl.p_discharge_coop[t] * dt_hours / (eta_d * storage_capacity)
                )
            return mdl.soc[t] == (
                mdl.soc[t - 1]
                + eta_c * mdl.p_charge[t] * dt_hours / storage_capacity
                - mdl.p_discharge_gt[t] * dt_hours / (eta_d * storage_capacity)
                - mdl.p_discharge_coop[t] * dt_hours / (eta_d * storage_capacity)
            )

        m.soc_evolution = pyomo.Constraint(m.T, rule=soc_evolution_rule)

        # Can't simultaneously discharge according to both G&T and COOP, or charge and discharge
        # at the same time.
        m.no_simultaneous = pyomo.Constraint(
            m.T,
            rule=lambda mdl, t: mdl.discharge_gt[t] + mdl.discharge_coop[t] + mdl.charge[t] <= 1,
        )

        # Can't charge during the dispatch window (or, when control_tier is set, the
        # Class A Peak Period).
        m.no_charge_in_window = pyomo.Constraint(
            m.T,
            rule=lambda mdl, t: (
                mdl.charge[t] == 0 if charge_restricted_w[t] else pyomo.Constraint.Skip
            ),
        )

        # Can't follow discharge commands from the co-op during the dispatch window (or,
        # when control_tier is set, the Class A Peak Period).
        m.no_discharge_coop_in_window = pyomo.Constraint(
            m.T,
            rule=lambda mdl, t: (
                mdl.discharge_coop[t] == 0 if charge_restricted_w[t] else pyomo.Constraint.Skip
            ),
        )

        # Meet consumer demand
        m.consumer_demand = pyomo.Constraint(
            m.T,
            rule=lambda mdl, t: (
                signal_d[t]
                == mdl.p_tocoop[t]
                + mdl.p_discharge_gt[t]
                + mdl.p_discharge_coop[t]
                - mdl.p_charge[t]
            ),
        )

        return m

    def _build_bill_min_model(
        self,
        window_start: int,
        window_len: int,
        init_soc: float,
        P_max: float,
        storage_capacity: float,
    ) -> pyomo.ConcreteModel:
        """Build the off-month Member bill-minimization MILP for a single rolling window.

        Solved instead of ``_build_dr_model`` for timesteps outside the
        Exclusive Control Months, where the Member
        has control of the battery.
        The battery is dispatched purely to reduce the Member's own energy
        and demand charges against ``demand_signal``. Charging is still
        disallowed during ``peak_window`` (the Class A Peak Period), same as
        in ``_build_dr_model``.

        Decision variables
        ------------------
        discharge[t] : binary
            Event indicator - 1 if discharging at timestep t.
        charge[t] : binary
            Event indicator - 1 if charging at timestep t.
        p_discharge[t] : continuous in [0, P_max]
            Actual discharge power (kW).
        p_charge[t] : continuous in [0, P_max]
            Actual charge power (kW).
        soc[t] : continuous in [soc_min, soc_max]
            State of charge (fraction).
        peak_demand[month] : continuous
            Peak net metered load (kW) during ``demand_charge_window`` that
            month - the demand-charge basis.

        Args:
            window_start (int): Timestep index of the first timestep in this window.
            window_len (int): Number of timesteps in this window.
            init_soc (float): State-of-charge fraction at the start of this window.
            P_max (float): Maximum charge/discharge rate (kW).
            storage_capacity (float): Total storage capacity (kWh).

        Returns:
            pyomo.ConcreteModel: Fully formed MILP ready to solve.
        """
        m: Any = pyomo.ConcreteModel(name="plm_bill_min")

        eta_c = self.config.charge_efficiency
        eta_d = self.config.discharge_efficiency
        soc_max = self.config.max_soc_fraction
        soc_min = self.config.min_soc_fraction
        dt_hours = self.dt_seconds / 3600.0

        w = slice(window_start, window_start + window_len)
        month_ids_w = self.month_ids[w]
        demand_w = np.asarray(self.config.demand_signal, dtype=float)[w]
        in_demand_window_w = self.in_demand_charge_window[w]
        in_peak_window_w = self.in_peak_window[w]

        months_in_window = sorted({int(mo) for mo in month_ids_w})

        m.T = pyomo.Set(initialize=range(window_len), doc="Timesteps in window")
        m.M = pyomo.Set(initialize=months_in_window, doc="Off-months in window")

        m.discharge = pyomo.Var(m.T, domain=pyomo.Binary, doc="1 if discharging at timestep t")
        m.charge = pyomo.Var(m.T, domain=pyomo.Binary, doc="1 if charging at timestep t")
        m.p_discharge = pyomo.Var(
            m.T, domain=pyomo.NonNegativeReals, bounds=(0, P_max), doc="Discharge power (kW)"
        )
        m.p_charge = pyomo.Var(
            m.T, domain=pyomo.NonNegativeReals, bounds=(0, P_max), doc="Charge power (kW)"
        )
        m.soc = pyomo.Var(
            m.T,
            domain=pyomo.NonNegativeReals,
            bounds=(soc_min, soc_max),
            doc="State of charge SoC_t",
        )
        m.peak_demand = pyomo.Var(
            m.M,
            domain=pyomo.NonNegativeReals,
            doc="Peak net metered load (kW) during the demand-charge window that month",
        )

        # peak_demand[month] >= net load at every (month, demand-window) timestep;
        # minimizing its coefficient in the objective drives it down to exactly the
        # month's single highest net load in that window - the demand-charge basis.
        m.demand_tracking = pyomo.ConstraintList()
        for month in months_in_window:
            for t in range(window_len):
                if month_ids_w[t] == month and in_demand_window_w[t]:
                    m.demand_tracking.add(
                        m.peak_demand[month] >= demand_w[t] - m.p_discharge[t] + m.p_charge[t]
                    )

        # Minimize the Member's own bill: flat energy charge on net metered load, plus
        # a combined demand+transmission charge on this window's highest net load
        # within demand_charge_window, for each month in the window.
        m.objective = pyomo.Objective(
            expr=self.config.energy_rate
            * dt_hours
            * sum((demand_w[t] - m.p_discharge[t] + m.p_charge[t]) for t in m.T)
            + self.config.demand_charge_rate
            * sum(m.peak_demand[month] for month in months_in_window),
            sense=pyomo.minimize,
        )

        m.discharge_power_link = pyomo.Constraint(
            m.T, rule=lambda mdl, t: mdl.p_discharge[t] <= P_max * mdl.discharge[t]
        )
        m.charge_power_link = pyomo.Constraint(
            m.T, rule=lambda mdl, t: mdl.p_charge[t] <= P_max * mdl.charge[t]
        )
        m.no_simultaneous = pyomo.Constraint(
            m.T, rule=lambda mdl, t: mdl.discharge[t] + mdl.charge[t] <= 1
        )

        # Can't charge during the Class A Peak Period, same restriction as the
        # Exclusive Control Month model.
        m.no_charge_in_peak_window = pyomo.Constraint(
            m.T,
            rule=lambda mdl, t: (
                mdl.charge[t] == 0 if in_peak_window_w[t] else pyomo.Constraint.Skip
            ),
        )

        m.soc_init = pyomo.Constraint(expr=m.soc[0] == init_soc)

        def soc_evolution_rule(mdl, t):
            prev_soc = init_soc if t == 0 else mdl.soc[t - 1]
            return mdl.soc[t] == (
                prev_soc
                + eta_c * mdl.p_charge[t] * dt_hours / storage_capacity
                - mdl.p_discharge[t] * dt_hours / (eta_d * storage_capacity)
            )

        m.soc_evolution = pyomo.Constraint(m.T, rule=soc_evolution_rule)

        return m

    def solve_dispatch_model(self, start_time: int = 0, n_days: int = 0):
        """Solve the DR MILP for the current window and record solver metrics.

        Args:
            start_time (int): Timestep index of the window start.
                Used only for error messages and metrics. Defaults to 0.
            n_days (int): Total simulation days. Passed to
                ``DispatchProblemState.store_problem_metrics``.
                Defaults to 0.

        Raises:
            RuntimeError: If solver returns a not OK status or an
                unacceptable termination condition.
        """

        solver_results = self.pyomosolver_solve_call(
            self.dr_model, self.config.pyomo_solver, self.config.pyomo_solver_options
        )

        status = solver_results.solver.status
        tc = solver_results.solver.termination_condition
        acceptable = (
            TerminationCondition.optimal,
            TerminationCondition.feasible,
            TerminationCondition.maxTimeLimit,
        )
        if status != SolverStatus.ok or tc not in acceptable:
            raise RuntimeError(
                f"PLM MILP solver failed at window start={start_time}: "
                f"status={status}, termination={tc}. "
                f"init_soc={self.updated_initial_soc:.4f}, "
                f"window_len={len(list(self.dr_model.T))}"
            )

        self.problem_state.store_problem_metrics(
            solver_results,
            start_time,
            n_days,
            pyomo.value(self.dr_model.objective),
        )

    @staticmethod
    def pyomosolver_solve_call(
        pyomo_model: pyomo.ConcreteModel,
        pyomo_solver: str = "highs",
        pyomo_solver_options: dict = {},
        log_name: str = "",
        user_solver_options: dict | None = None,
    ):
        """Solve a Pyomo MILP with highs

        Args:
            pyomo_model (pyomo.ConcreteModel): The model to solve.
            log_name (str): Optional log file name passed to
                ``SolverOptions``. Defaults to ``''``.
            user_solver_options (dict | None): Optional overrides for
                highs solver options. Defaults to ``None``.

        Returns:
            pyomo.opt.SolverResults: Raw results object from highs.
        """
        default_solver_specs = {
            "highs": {
                "time_limit": 300,
                "presolve": "on",
            },
            "glpk": {"cuts": None, "presol": None, "tmlim": 300},
        }
        default_solver_spec_options = default_solver_specs[pyomo_solver]
        # Update the default_solver_spec_options with pyomo_solver_options from input configuration
        # Note that the syntax `A|B` uses values from B for keys that exist in both A and B.
        solver_spec_options = default_solver_spec_options | pyomo_solver_options

        solver_options = SolverOptions(solver_spec_options, log_name, user_solver_options, "log")

        with pyomo.SolverFactory(pyomo_solver) as solver:
            results = solver.solve(pyomo_model, options=solver_options.constructed, tee=False)
        return results

    def _get_storage_dispatch_commands(self) -> list:
        """Net dispatch commands for the solved window.

        Works for either model built by this controller: the  MILP
        from ``_build_dr_model``, or
        the off-month bill-minimization MILP from ``_build_bill_min_model``.

        Returns:
            list[float]: ``p_discharge_t - p_charge_t`` (kW) for each timestep
            in the solved window. Positive = discharge, negative = charge.
        """
        if hasattr(self.dr_model, "p_discharge_gt"):
            return [
                pyomo.value(self.dr_model.p_discharge_gt[t])
                + pyomo.value(self.dr_model.p_discharge_coop[t])
                - pyomo.value(self.dr_model.p_charge[t])  # type: ignore[index]
                for t in self.dr_model.T
            ]
        return [
            pyomo.value(self.dr_model.p_discharge[t]) - pyomo.value(self.dr_model.p_charge[t])  # type: ignore[index]
            for t in self.dr_model.T
        ]

    def _GnT_pricingfunction(self, lmp: float) -> float:
        """Compute the cost a G&T charges to a Coop based on the current grid price.

        Args:
            lmp (float): Current grid price (locational marginal price), e.g., in $/kWh.

        Returns:
            float: Cost charged by the G$T in the same units as `lmp`.
        """
        num_coeffs = len(self.config.GnT_pricingfunction_coeffs)
        price = 0.0
        for idx_coeff in range(num_coeffs):
            price += self.config.GnT_pricingfunction_coeffs[idx_coeff] * lmp ** (
                num_coeffs - 1 - idx_coeff
            )

        return price
