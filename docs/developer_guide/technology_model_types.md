(technology_model_types)=
# Technology Model Types

## Performance model

This OpenMDAO system contains the physics model for the technology.
For a converter, this computes the outputted resources based on the inputted resources.

For example, for an electrolyzer, the performance model is an OpenMDAO system whose inputs include electricity and whose outputs include hydrogen produced.

Here is an example of a solar PV performance model.

```python
import PySAM.Pvwattsv8 as Pvwatts
from attrs import field, define

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.core.validators import contains, range_val_or_none
from h2integrate.converters.solar.solar_baseclass import SolarPerformanceBaseClass


@define(kw_only=True)
class PYSAMSolarPlantPerformanceModelDesignConfig(BaseConfig):
    """Performance-model configuration for ``PYSAMSolarPlantPerformanceModel``.

    Fields declared here are validated against the user inputs supplied in
    ``tech_config['model_inputs']['performance_parameters']`` (or the shared
    block) when ``from_dict`` is called in ``setup``.
    """

    pv_capacity_kWdc: float = field()
    dc_ac_ratio: float = field(default=None, validator=range_val_or_none(0.0, 2.0))
    tilt: float = field(default=None, validator=range_val_or_none(0.0, 90.0))
    config_name: str = field(
        default="PVWattsSingleOwner",
        validator=contains(["PVWattsSingleOwner", "PVWattsCommercial"]),  # truncated
    )


class PYSAMSolarPlantPerformanceModel(SolarPerformanceBaseClass):
    """OpenMDAO component wrapping PySAM's PVWatts v8 model."""

    def setup(self):
        super().setup()

        # Build a validated configuration object from user inputs.
        self.design_config = PYSAMSolarPlantPerformanceModelDesignConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance"),
            strict=True,
            additional_cls_name=self.__class__.__name__,
        )

        # Register any extra I/O beyond what the baseclass already provides.
        self.add_input(
            "system_capacity_DC",
            val=self.design_config.pv_capacity_kWdc,
            units="kW",
            desc="PV rated capacity in DC",
        )
        self.add_output("system_capacity_AC", val=0.0, units="kW")

        self.system_model = Pvwatts.new(self.design_config.config_name)
        # ...assign design parameters to ``self.system_model``...

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        # ...push inputs and solar resource into the PySAM model...
        self.system_model.value("system_capacity", inputs["system_capacity_DC"][0])
        self.system_model.value("solar_resource_data", discrete_inputs["solar_resource_data"])
        self.system_model.execute(0)

        # Write the standard production outputs declared by SolarPerformanceBaseClass.
        outputs["electricity_out"] = self.system_model.Outputs.gen
        outputs["system_capacity_AC"] = (
            self.system_model.value("system_capacity")
            / self.system_model.value("dc_ac_ratio")
        )
        outputs["rated_electricity_production"] = outputs["system_capacity_AC"]
        outputs["total_electricity_produced"] = (
            outputs["electricity_out"].sum() * (self.dt / 3600)
        )
        outputs["annual_electricity_produced"] = self.system_model.value("ac_annual")

        # Flexible models must apply curtailment at the end of compute(). This
        # clips ``{commodity}_out`` to ``min(uncurtailed, command_value)`` and
        # copies the raw output into ``uncurtailed_{commodity}_out``. It is a
        # no-op when no upstream controller is configured.
        self.apply_curtailment(outputs)
```

See `h2integrate/converters/solar/solar_pysam.py` for the full implementation,
including tilt-angle and resource-data handling.


## Cost model

This is an OpenMDAO system containing the cost model.
Specifically, this system must output `CapEx` and `OpEx` values for the technology.
These values are later used in financial modeled and cost breakdowns.

Cost models follow the same pattern as performance models, but inherit from
`CostModelBaseClass` and use a `CostModelBaseConfig` (or `BaseConfig`)
configuration class. `CostModelBaseClass` registers the required `CapEx`,
`OpEx`, and `cost_year` outputs; no inputs are predefined.

If the dollar-year for the costs is **inherent to the cost model** (i.e. the
model always reports costs in a fixed dollar-year), inherit the config from
`BaseConfig` and pin `cost_year` to a constant:

```python
from attrs import field, define

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.core.validators import gt_zero, must_equal
from h2integrate.core.model_baseclasses import CostModelBaseClass


@define(kw_only=True)
class ReverseOsmosisCostModelConfig(BaseConfig):
    # Config values come from tech_config['model_inputs']['cost_parameters']
    # or tech_config['model_inputs']['shared_parameters'].
    freshwater_kg_per_hour: float = field(validator=gt_zero)
    freshwater_density: float = field(validator=gt_zero)
    # cost_year is fixed because this model always reports 2013 USD.
    cost_year: int = field(default=2013, converter=int, validator=must_equal(2013))


class ReverseOsmosisCostModel(CostModelBaseClass):
    def setup(self):
        self.config = ReverseOsmosisCostModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost"),
            additional_cls_name=self.__class__.__name__,
        )
        super().setup()

        self.add_input(
            "plant_capacity_kgph", val=0.0, units="kg/h", desc="Desired freshwater flow rate"
        )

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        capex = 32894 * (self.config.freshwater_kg_per_hour / 3600)  # USD
        opex = 4841 * (self.config.freshwater_kg_per_hour / 3600)    # USD/yr
        outputs["CapEx"] = capex
        outputs["OpEx"] = opex
```

If the dollar-year for the costs **depends on user inputs in `tech_config`**,
inherit the config from `CostModelBaseConfig` instead. `CostModelBaseConfig`
adds a required `cost_year` field, forcing the user to supply it:

```python
from attrs import field, define

from h2integrate.core.utilities import merge_shared_inputs
from h2integrate.core.validators import gt_zero
from h2integrate.core.model_baseclasses import CostModelBaseClass, CostModelBaseConfig


@define(kw_only=True)
class ATBUtilityPVCostModelConfig(CostModelBaseConfig):
    capex_per_kWac: float | int = field(validator=gt_zero)
    opex_per_kWac_per_year: float | int = field(validator=gt_zero)
    # ``cost_year`` is inherited from CostModelBaseConfig and is user-provided.


class ATBUtilityPVCostModel(CostModelBaseClass):
    def setup(self):
        self.config = ATBUtilityPVCostModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost"),
            additional_cls_name=self.__class__.__name__,
        )
        super().setup()

        self.add_input("system_capacity_AC", val=0.0, units="kW", desc="PV rated capacity in AC")

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        capacity = inputs["system_capacity_AC"][0]
        outputs["CapEx"] = self.config.capex_per_kWac * capacity
        outputs["OpEx"] = self.config.opex_per_kWac_per_year * capacity
```

## Control model (optional)

Every technology group in H2Integrate contains a controller subsystem that converts a `{commodity}_set_point` signal into the `{commodity}_command_value` consumed by the performance model. If you do not specify a `control_strategy` for your technology, H2Integrate automatically inserts a `PassthroughController` that simply copies set-point to command value, so most new performance models do not need a custom controller.

You only need to write a control model if you want to override that default — for example, to implement a heuristic or optimized dispatch strategy for a storage technology. The process is similar to the performance model: the controller's required inputs and outputs (`{commodity}_set_point` in, `{commodity}_command_value` out) are defined in the relevant control baseclass. See the [technology-level control overview](../control/technology_level_control/technology_control_overview.md) for available frameworks and supported controllers.

```{note}
It is possible to have a combined performance, cost, and financial model within a single OpenMDAO system, provided that it returns all the necessary values.
For example, in the HOPP wrapper, we use a combined performance and cost model to reduce computational cost.
```

## Financial model (optional)

Each technology class can define an OpenMDAO system containing the financial model.
This would override any plant level financial model, and is useful for technologies that have unique financial considerations.
This could also be more relevant as we develop non-single-owner capabilities.
