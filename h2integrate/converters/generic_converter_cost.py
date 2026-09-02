from attrs import field, define, validators

from h2integrate.core.utilities import merge_shared_inputs
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
        additional_capex_USD (float | int, optional): additional capital expense that does not
            scale with the input commodity rated production. In units of USD. Defaults to 0.
        additional_opex_USD_per_year (float | int, optional): additional annual fixed operating
            expense that does not scale with the input commodity rated production.
            In units of USD/year. Defaults to 0.
        additional_varopex_USD_per_year (float | int, optional): additional annual variable
            operating expense that does not scale with the input commodity annual production.
            In units of USD/year. Defaults to 0.
    """

    commodity: str = field(converter=str.strip)
    commodity_rate_units: str = field(converter=str.strip)
    unit_capex: float | int = field(validator=validators.ge(0))
    unit_varopex: float = field()

    unit_opex: float | int | None = field(default=None)
    opex_fraction: float | None = field(
        default=None, validator=validators.optional((validators.ge(0), validators.le(1)))
    )
    commodity_amount_units: str = field(default=None)

    additional_capex_USD: float | int = field(default=0.0)
    additional_opex_USD_per_year: float | int = field(default=0.0)
    additional_varopex_USD_per_year: float | int = field(default=0.0)

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
            shape=self.plant_life,
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

        self.add_input(
            "additional_constant_capex",
            val=self.config.additional_capex_USD,
            units="USD",
            desc="Additional capital expense",
        )
        self.add_input(
            "additional_constant_opex",
            val=self.config.additional_opex_USD_per_year,
            units="USD/year",
            desc="Additional annual fixed operating expense",
        )
        self.add_input(
            "additional_constant_varopex",
            val=self.config.additional_varopex_USD_per_year,
            shape=self.plant_life,
            units="USD/year",
            desc="Additional annual variable operating expense",
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
        outputs["CapEx"] = tot_capex + inputs["additional_constant_capex"]
        if "unit_opex" in inputs:
            opex = inputs[f"rated_{self.config.commodity}_production"] * inputs["unit_opex"]
        else:
            opex = tot_capex * inputs["fixed_opex_ratio"]

        outputs["OpEx"] = opex + inputs["additional_constant_opex"]
        outputs["VarOpEx"] = (
            inputs[f"annual_{self.config.commodity}_produced"] * inputs["unit_varopex"]
        ) + inputs["additional_constant_varopex"]
