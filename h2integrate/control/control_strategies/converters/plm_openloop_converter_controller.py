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
    Configuration class for the PeakLoadManagementHeuristicOpenLoopStorageController.

    Defines peak-selection and dispatch-priority rules used to pre-compute
    an open-loop discharge and recharge schedule.

    Attributes:
        system_capacity_kw (int | float): Maximum converter command value allowed by
            this controller, in commodity rate units (for example, kW or kg/h).
        demand_profile_peak_cutoff (int | float): Primary set-point threshold used to
            trigger demand curtailment. Dispatch is only considered when
            ``<commodity>_set_point`` exceeds this value.
        demand_profile_upstream (int | float | list | None): Secondary upstream profile
            used to trigger or shape dispatch decisions. For
            ``demand_profile_upstream_kind='electricity'`` this is typically an
            upstream demand signal in commodity amount units. For
            ``demand_profile_upstream_kind='price'`` this is a price time series.
        demand_profile_upstream_peak_cutoff (int | float | None): Threshold applied to
            ``demand_profile_upstream``. Units depend on
            ``demand_profile_upstream_kind``.
        demand_profile_upstream_kind (str): Interpretation mode for
            ``demand_profile_upstream``. One of ``"electricity"`` or ``"price"``.
            Defaults to ``"electricity"``.

    """

    system_capacity_kw: int | float = field()
    demand_profile_peak_cutoff: int | float = field()
    demand_profile_upstream: int | float | list | None = field()
    demand_profile_upstream_peak_cutoff: int | float | None = field()
    demand_profile_upstream_kind: str = field(
        default="electricity", validator=contains(["electricity", "price"])
    )

    def __attrs_post_init__(self):
        super().__attrs_post_init__()


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

    def setup(self):
        """Initialize configuration and register converter-specific OpenMDAO inputs.

        During setup:
        1. Loads controller configuration from tech_config model inputs
        2. Registers a converter capacity input
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
            f"system_capacity_{self.config.commodity_rate_units}",
            val=self.config.system_capacity_kw,
            units=f"{self.config.commodity_rate_units}",
            desc="Converter control system awareness of the system capacity",
        )

        if self.config.demand_profile_upstream_kind == "price":
            peak_cutoff_units = f"USD/({self.config.commodity_amount_units})"
        else:
            peak_cutoff_units = self.config.commodity_amount_units

        self.add_input(
            "demand_profile_upstream_peak_cutoff",
            val=self.config.demand_profile_upstream_peak_cutoff,
            units=peak_cutoff_units,
            desc="demand_profile_upstream_peak_cutoff",
        )

        self.n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]

    def compute(self, inputs, outputs):
        """Compute converter command profile using configured peak-cutoff heuristics.

        Dispatch logic per timestep:

        - If the primary set-point exceeds demand_profile_peak_cutoff,
          dispatch may be activated.
        - For ``demand_profile_upstream_kind='electricity'``, the command tracks
          the larger of primary and upstream exceedances, while respecting demand
          and capacity limits.
        - For ``demand_profile_upstream_kind='price'``, dispatch is only enabled
          when upstream price exceeds demand_profile_upstream_peak_cutoff.

        The command is clipped to remain between zero and both the instantaneous
        demand and converter capacity.

        Args:
            inputs: OpenMDAO input vector containing set-point, upstream cutoff,
                and converter capacity values.
            outputs: OpenMDAO output vector populated with
                ``<commodity>_command_value``.

        Raises:
            ValueError: If demand_profile_upstream_kind is neither
                ``"electricity"`` nor ``"price"``.
        """
        commodity = self.config.commodity
        demand_profile = inputs[f"{commodity}_set_point"]
        system_capacity_rate = inputs[f"system_capacity_{self.config.commodity_rate_units}"][0]
        demand_profile_peak_cutoff = self.config.demand_profile_peak_cutoff
        demand_profile_upstream = self.config.demand_profile_upstream
        demand_profile_upstream_peak_cutoff = inputs["demand_profile_upstream_peak_cutoff"][0]
        self.command_value = np.zeros(self.n_timesteps)

        for idx, val in enumerate(demand_profile):
            val_upstream = demand_profile_upstream[idx]
            if (
                val > demand_profile_peak_cutoff
                or val_upstream > demand_profile_upstream_peak_cutoff
            ):
                desired_dispatch = val - demand_profile_peak_cutoff

                if self.config.demand_profile_upstream_kind == "electricity":
                    desired_dispatch_upstream = val_upstream - demand_profile_upstream_peak_cutoff

                    self.command_value[idx] = min(
                        max(
                            max(desired_dispatch, 0),
                            max(desired_dispatch_upstream, 0),
                        ),
                        val,
                        system_capacity_rate,
                    )
                elif self.config.demand_profile_upstream_kind == "price":
                    if val_upstream > demand_profile_upstream_peak_cutoff:
                        self.command_value[idx] = min(
                            max(desired_dispatch, 0),
                            val,
                            system_capacity_rate,
                        )
                else:
                    raise (
                        ValueError(
                            f"Invalid demand_profile_upstream_kind \
                            '{self.config.demand_profile_upstream_kind}'"
                        )
                    )

        outputs[f"{commodity}_command_value"] = self.command_value
