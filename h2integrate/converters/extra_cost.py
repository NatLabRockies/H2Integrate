from attrs import field, define

from h2integrate.core.utilities import merge_shared_inputs
from h2integrate.core.validators import range_val_or_none
from h2integrate.core.model_baseclasses import CostModelBaseClass, CostModelBaseConfig


@define(kw_only=True)
class ExtraExpenseCostConfig(CostModelBaseConfig):
    """Configuration class for the ExtraExpenseCostModel with costs expressed in dollars.

    Attributes:
        capital_cost_USD (float | int): capital cost in USD.
        variable_opex_cost_USD_per_year (float | int): variable O&M cost in USD/year.
        opex_cost_USD_per_year (float | int | None): fixed O&M cost in units of `USD/year`.
            Only required if `opex_cost_fraction_of_capex` is None. Defaults to None.
        opex_cost_fraction_of_capex (float | int | None): the fixed O&M cost as a ratio of CapEx.
            Must be between 0 or 1. Only required if `opex_cost_USD_per_year` is None.
            Defaults to None.
        cost_year (int): dollar year of input costs
    """

    capital_cost_USD: float | int = field()
    variable_opex_cost_USD_per_year: float | int = field()
    opex_cost_USD_per_year: float | None = field(default=None)
    opex_cost_fraction_of_capex: float | None = field(
        default=None, validator=range_val_or_none(0, 1)
    )

    def __attrs_post_init__(self):
        # If both or neither OpEx value was input, raise an error
        if (self.opex_cost_USD_per_year is None and self.opex_cost_fraction_of_capex is None) or (
            self.opex_cost_USD_per_year is not None and self.opex_cost_fraction_of_capex is not None
        ):
            msg = (
                "Please provide either a value for `opex_cost_USD_per_year` or a value for "
                + "`opex_cost_fraction_of_capex` in the `ExtraExpenseCostConfig`, but not both."
            )
            raise KeyError(msg)


class ExtraExpenseCostModel(CostModelBaseClass):
    _time_step_bounds = (
        1,
        1e9,
    )  # (min, max) time step lengths (in seconds) compatible with this model

    def setup(self):
        self.config = ExtraExpenseCostConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost"),
            strict=True,
            additional_cls_name=self.__class__.__name__,
        )

        super().setup()

        # Cost parameter inputs
        self.add_input(
            "capital_cost",
            val=self.config.capital_cost_USD,
            units="USD",
            desc="Unit CapEx",
        )

        self.add_input(
            "varopex_cost",
            val=self.config.variable_opex_cost_USD_per_year,
            units="USD/year",
            desc="Unit Variable O&M",
        )

        if self.config.opex_cost_fraction_of_capex is not None:
            # opex is expressed as a fraction of CapEx
            self.add_input(
                "fixed_opex_ratio",
                val=self.config.opex_cost_fraction_of_capex,
                units="unitless",
                desc="Fixed OpEx as a fraction of the total CapEx",
            )
        else:
            # opex is expressed as a dollar amount
            self.add_input(
                "fixed_opex_cost",
                val=self.config.opex_cost_USD_per_year,
                units="USD/year",
                desc="Unit Fixed OpEx",
            )

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        outputs["CapEx"] = inputs["capital_cost"]

        if "fixed_opex_ratio" in inputs:
            outputs["OpEx"] = outputs["CapEx"] * inputs["fixed_opex_ratio"]
        else:
            outputs["OpEx"] = inputs["fixed_opex_cost"]

        outputs["VarOpEx"] = inputs["fixed_opex_cost"]
