import openmdao.api as om


class PassthroughController(om.ExplicitComponent):
    """Simple controller that passes a demand signal directly through as a set-point.

    Every technology group is expected to have a controller subsystem. When a
    technology does not define its own ``control_strategy``, this passthrough
    controller is inserted automatically so that the group exposes a uniform
    ``{commodity}_demand`` input and ``{commodity}_set_point`` output interface.

    In a system-level-control (SLC) configuration the SLC output is connected to
    ``{commodity}_demand``; this component copies that signal to
    ``{commodity}_set_point`` which the performance model consumes.

    When no SLC is present the input defaults to a very large value so that
    production is unconstrained, making the component a harmless no-op.
    """

    _time_step_bounds = (0, float("inf"))

    def initialize(self):
        self.options.declare("commodity", types=str)
        self.options.declare("n_timesteps", types=int)
        self.options.declare(
            "commodity_rate_units",
            types=str,
            default=None,
            desc="Units for the commodity rate (e.g. 'kW', 'kg/h'). "
            "When provided, explicit units are used on the demand input "
            "so the variable works even when unconnected (no SLC). "
            "The set-point output always uses units_by_conn to inherit "
            "units from the connected performance model.",
        )

    def setup(self):
        commodity = self.options["commodity"]
        n_timesteps = self.options["n_timesteps"]
        commodity_rate_units = self.options["commodity_rate_units"]

        # Use explicit units on the input when available so that the
        # variable remains valid even when no SLC is connected
        # (units_by_conn fails on unconnected variables).
        # Default to a large value so that when no SLC is connected the
        # downstream performance model behaves as if unconstrained (the perf
        # model typically saturates the set-point at its rated capacity).
        # We avoid extreme values (e.g. 1e30) here because they pollute the
        # NLBGS relative-residual check and cause premature false convergence
        # in cyclic system-level control configurations.
        default_val = 1.0e9

        if commodity_rate_units is not None:
            self.add_input(
                f"{commodity}_demand",
                val=default_val,
                shape=n_timesteps,
                desc=f"Demand signal for {commodity}",
                units=commodity_rate_units,
            )
        else:
            self.add_input(
                f"{commodity}_demand",
                val=default_val,
                shape=n_timesteps,
                desc=f"Demand signal for {commodity}",
                units_by_conn=True,
            )

        if commodity_rate_units is not None:
            self.add_output(
                f"{commodity}_set_point",
                val=default_val,
                shape=n_timesteps,
                desc=f"Set point for {commodity} (passthrough of demand)",
                units=commodity_rate_units,
            )
        else:
            self.add_output(
                f"{commodity}_set_point",
                val=default_val,
                shape=n_timesteps,
                desc=f"Set point for {commodity} (passthrough of demand)",
                units_by_conn=True,
            )

    def compute(self, inputs, outputs):
        commodity = self.options["commodity"]
        outputs[f"{commodity}_set_point"] = inputs[f"{commodity}_demand"]
