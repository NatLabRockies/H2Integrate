import numpy as np
from attrs import field, define

from h2integrate.core.utilities import merge_shared_inputs
from h2integrate.core.validators import contains
from h2integrate.control.control_strategies.storage.openloop_storage_control_base import (
    StorageOpenLoopControlBase,
    StorageOpenLoopControlBaseConfig,
)


@define(kw_only=True)
class PeakLoadManagementHeuristicOpenLoopConverterControllerConfig(
    StorageOpenLoopControlBaseConfig
):
    """
    Configuration class for the PeakLoadManagementHeuristicOpenLoopConverterController.

    Defines the peak-cutoff heuristics used to compute an open-loop converter
    command that shaves demand peaks from one or two demand profiles.

    Attributes:
        demand_profile_peak_cutoff (int | float): Primary set-point threshold used to
            trigger demand curtailment. Dispatch is only considered when
            ``<commodity>_set_point`` exceeds this value.
        demand_profile_upstream (int | float | list | None): Secondary upstream profile
            used to trigger or shape dispatch decisions. For
            ``demand_profile_upstream_kind='commodity'`` this is typically an
            upstream demand signal in commodity amount units. For
            ``demand_profile_upstream_kind='price'`` this is a price time series.
        demand_profile_upstream_peak_cutoff (int | float | None): Threshold applied to
            ``demand_profile_upstream``. Units depend on
            ``demand_profile_upstream_kind``.
        demand_profile_upstream_kind (str): Interpretation mode for
            ``demand_profile_upstream``. One of ``"commodity"`` or ``"price"``.
            Defaults to ``"commodity"``.

    """

    demand_profile_peak_cutoff: int | float = field()
    demand_profile_upstream: int | float | list | None = field()
    demand_profile_upstream_peak_cutoff: int | float | None = field()
    demand_profile_upstream_kind: str = field(
        default="commodity", validator=contains(["commodity", "price"])
    )


class PeakLoadManagementHeuristicOpenLoopConverterController(StorageOpenLoopControlBase):
    """Open-loop peak-load management controller for converter technologies.

    This controller computes a timestep-wise converter command that limits
    dispatch based on:
    1. A primary set-point peak cutoff
    2. An optional upstream signal cutoff (electricity demand or price)
    3. A converter capacity ceiling

    The resulting command profile is written to ``<commodity>_command_value`` and
    can be consumed by converter performance models.
    """

    _time_step_bounds = (
        1e-12,
        np.inf,
    )

    # This controller reads the performance model's ``rated_<commodity>_production``
    # output as its command ceiling, which creates a controller<->performance data
    # cycle within the technology group. h2integrate_model.py::_process_model() checks
    # this flag and adds a nonlinear solver so the cycle converges if needed.
    _reads_performance_outputs = True

    def setup(self):
        """Initialize configuration and register converter-specific OpenMDAO inputs.

        During setup:
        1. Loads controller configuration from tech_config model inputs
        2. Registers a rated-production input (auto-connected to the technology's
        performance-model ``rated_<commodity>_production`` output via promotion)
        3. Registers an upstream cutoff input with units based on
        demand_profile_upstream_kind
        4. Stores the simulation horizon length for use in compute()

        """
        self.config = PeakLoadManagementHeuristicOpenLoopConverterControllerConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "control"),
            strict=False,
            additional_cls_name=self.__class__.__name__,
        )
        super().setup()

        self.add_input(
            f"rated_{self.config.commodity}_production",
            val=0.0,
            units=f"{self.config.commodity_rate_units}",
            desc="Rated production of the technology, used as the converter command ceiling",
        )

        if self.config.demand_profile_upstream_kind == "price":
            peak_cutoff_units = f"USD/({self.config.commodity_amount_units})"
        else:
            peak_cutoff_units = self.config.commodity_rate_units
        self.add_input(
            "demand_profile_upstream_peak_cutoff",
            val=self.config.demand_profile_upstream_peak_cutoff,
            units=peak_cutoff_units,
            desc="demand_profile_upstream_peak_cutoff",
        )

    def compute(self, inputs, outputs):
        """Compute converter command profile using configured peak-cutoff heuristics.

        Dispatch logic per timestep:
        - If the primary set-point exceeds demand_profile_peak_cutoff,
        dispatch may be activated.
        - For ``demand_profile_upstream_kind='commodity'``, the command tracks
        the larger of primary and upstream exceedances, while respecting demand
        and capacity limits.
        - For ``demand_profile_upstream_kind='price'``, dispatch is only enabled
        when upstream price exceeds demand_profile_upstream_peak_cutoff.

        The command is clipped to remain between zero and both the instantaneous
        demand and converter capacity.

        Args:
            inputs: OpenMDAO input vector containing set-point, upstream cutoff,
                and rated-production values.
            outputs: OpenMDAO output vector populated with
                ``<commodity>_command_value``.

        Raises:
            ValueError: If demand_profile_upstream_kind is neither
                ``"commodity"`` nor ``"price"``.
        """
        commodity = self.config.commodity
        demand_profile = inputs[f"{commodity}_set_point"]
        rated_production = inputs[f"rated_{commodity}_production"][0]
        demand_profile_peak_cutoff = self.config.demand_profile_peak_cutoff
        demand_profile_upstream = self.config.demand_profile_upstream
        demand_profile_upstream_peak_cutoff = inputs["demand_profile_upstream_peak_cutoff"][0]
        self.command_value = np.zeros(self.n_timesteps)

        if demand_profile_upstream is None:
            demand_profile_upstream = np.zeros_like(demand_profile)
        else:
            demand_profile_upstream = np.asarray(demand_profile_upstream)
            if demand_profile_upstream.ndim == 0:
                demand_profile_upstream = np.full_like(
                    demand_profile, float(demand_profile_upstream)
                )

        for idx, val in enumerate(demand_profile):
            val_upstream = demand_profile_upstream[idx]
            if (
                val > demand_profile_peak_cutoff
                or val_upstream > demand_profile_upstream_peak_cutoff
            ):
                desired_dispatch = val - demand_profile_peak_cutoff

                if self.config.demand_profile_upstream_kind == "commodity":
                    desired_dispatch_upstream = val_upstream - demand_profile_upstream_peak_cutoff

                    self.command_value[idx] = min(
                        max(
                            max(desired_dispatch, 0),
                            max(desired_dispatch_upstream, 0),
                        ),
                        val,
                        rated_production,
                    )
                elif self.config.demand_profile_upstream_kind == "price":
                    if val_upstream > demand_profile_upstream_peak_cutoff:
                        self.command_value[idx] = min(
                            max(desired_dispatch, 0),
                            val,
                            rated_production,
                        )
                else:
                    raise (
                        ValueError(
                            f"Invalid demand_profile_upstream_kind \
                            '{self.config.demand_profile_upstream_kind}'"
                        )
                    )

        outputs[f"{commodity}_command_value"] = self.command_value
