from attrs import field, define

from h2integrate.core.utilities import merge_shared_inputs
from h2integrate.core.validators import gte_zero, range_val_or_none
from h2integrate.core.model_baseclasses import CostModelBaseClass, CostModelBaseConfig


@define(kw_only=True)
class GenericConverterCostConfig(CostModelBaseConfig):
    """Configuration class for the GenericConverterCostModel with costs based on rated capacity.
    The cost units must compatible with the units of the commodity produced by the converter.

    Attributes:
        commodity (str): name of commodity
        commodity_rate_units (str): Units of the commodity (e.g., "kg/h" or "kW").
        unit_capex (float | int): capital cost in units of `USD/commodity_rate_units`.
            Must be greater than or equal to zero.
        unit_varopex (float | int): variable O&M cost in units of `USD/commodity_amount_units`
        unit_opex (float | int | None): fixed O&M cost in units of `USD/commodity_rate_units/year`.
            Only required if `opex_fraction` is None. Defaults to None.
        opex_fraction (float | int | None): the fixed O&M cost as a ratio of the CapEx.
            Must be between 0 or 1. Only required if `unit_opex` is None. Defaults to None.
        cost_year (int): dollar year of input costs
        commodity_amount_units (str | None, optional): Units of the commodity as an amount
            (i.e., "kW*h" or "kg"). If not provided, defaults to `commodity_rate_units*h`.
    """

    commodity: str = field(converter=str.strip)
    commodity_rate_units: str = field(converter=str.strip)
    unit_capex: float | int = field(validator=gte_zero)
    unit_varopex: float = field()

    unit_opex: float | int | None = field(default=None)
    opex_fraction: float | None = field(default=None, validator=range_val_or_none(0, 1))
    commodity_amount_units: str = field(default=None)

    def __attrs_post_init__(self):
        # If both or neither OpEx value was input, raise an error
        if (self.unit_opex is None and self.opex_fraction is None) or (
            self.unit_opex is not None and self.opex_fraction is not None
        ):
            msg = (
                "Please provide either a value for `unit_opex` or a value for "
                + "`opex_fraction` in the generic converter cost config, but not both."
            )
            raise KeyError(msg)

        if self.commodity_amount_units is None:
            self.commodity_amount_units = f"({self.commodity_rate_units})*h"


class GenericConverterCostModel(CostModelBaseClass):
    _time_step_bounds = (
        3600,
        3600,
    )  # (min, max) time step lengths (in seconds) compatible with this model

    def setup(self):
        self.config = GenericConverterCostConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost"),
            strict=True,
            additional_cls_name=self.__class__.__name__,
        )
        plant_life = int(self.options["plant_config"]["plant"]["plant_life"])

        super().setup()

        # Inputs that are outputs of the performance model
        self.add_input(
            f"rated_{self.config.commodity}_production",
            val=0.0,
            units=self.config.commodity_rate_units,
        )
        self.add_input(
            f"annual_{self.config.commodity}_produced",
            val=0.0,
            shape=plant_life,
            units=f"({self.config.commodity_amount_units})/year",
        )

        # Cost parameter inputs
        self.add_input(
            "unit_capex",
            val=self.config.unit_capex,
            units=f"USD/({self.config.commodity_rate_units})",
            desc="Unit CapEx",
        )

        self.add_input(
            "unit_varopex",
            val=self.config.unit_varopex,
            units=f"USD/({self.config.commodity_amount_units})",
            desc="Unit Variable O&M",
        )

        if self.config.opex_fraction is not None:
            # opex is expressed as a fraction of CapEx
            self.add_input(
                "fixed_opex_ratio",
                val=self.config.opex_fraction,
                units="unitless",
                desc="Fixed OpEx as a fraction of the total CapEx",
            )
        else:
            # opex is expressed as a multiplier of rated capacity
            self.add_input(
                "unit_opex",
                val=self.config.unit_opex,
                units=f"USD/({self.config.commodity_rate_units})/year",
                desc="Unit Fixed OpEx",
            )

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        tot_capex = inputs[f"rated_{self.config.commodity}_production"] * inputs["unit_capex"]
        outputs["CapEx"] = tot_capex
        if "unit_opex" in inputs:
            outputs["OpEx"] = (
                inputs[f"rated_{self.config.commodity}_production"] * inputs["unit_opex"]
            )
        else:
            outputs["OpEx"] = tot_capex * inputs["fixed_opex_ratio"]
        outputs["VarOpEx"] = (
            inputs[f"annual_{self.config.commodity}_produced"] * inputs["unit_varopex"]
        )
