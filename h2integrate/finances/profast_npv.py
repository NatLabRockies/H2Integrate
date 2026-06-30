from openmdao.utils.units import convert_units

from h2integrate.finances.tools import _compute_rate_units
from h2integrate.finances.profast_base import ProFastBase


class ProFastNPV(ProFastBase):
    """Calculates the Net Present Value (NPV) of a commodity using ProFAST.

    This component extends `ProFastBase` to compute the NPV based on the user-defined
    commodity and its sell price. The NPV output reflects the present value of future
    cash flows, given the financial configuration of the plant.

    Attributes:
        output_txt (str): Label used for naming outputs based on commodity type.
        lco_units (str): Units for pricing inputs (USD/kg or USD/kWh, depending on commodity).

    Outputs:
        NPV_<commodity> (float): Net Present Value of the commodity in USD.
    """

    def add_model_specific_outputs(self):
        """Define NPV output variable for the model.

        Creates an output variable named `NPV_<commodity>` in USD.

        Returns:
            None
        """
        self.add_output(
            f"NPV_{self.output_txt}",
            val=0.0,
            units="USD",
        )

        return

    def setup(self):
        """Set up inputs for the NPV calculation.

        Retrieves the commodity sell price and its units from the plant configuration
        and registers it as an input for the component. Calls the base `setup()` method
        to initialize other ProFAST inputs and outputs.

        Raises:
            ValueError: If `commodity_sell_price` or `commodity_sell_price_units` is not
                provided in the configuration.

        Returns:
            None
        """
        model_inputs = self.options["plant_config"]["finance_parameters"]["model_inputs"]
        self.commodity_sell_price = model_inputs.get("commodity_sell_price", None)
        self.commodity_sell_price_units = model_inputs.get("commodity_sell_price_units", None)

        if self.commodity_sell_price is None:
            raise ValueError("commodity_sell_price is missing as an input")
        if self.commodity_sell_price_units is None:
            raise ValueError(
                "commodity_sell_price_units is missing as an input. "
                "ProFastNPV requires the user to specify the units of "
                "commodity_sell_price explicitly in "
                "plant_config['finance_parameters']['model_inputs']."
            )

        super().setup()

        self.add_input(
            f"sell_price_{self.output_txt}",
            val=self.commodity_sell_price,
            units=self.commodity_sell_price_units,
        )

    def compute(self, inputs, outputs):
        """Compute the NPV of the commodity using ProFAST cash flows.

        Args:
            inputs (dict): Model inputs, including `sell_price_<commodity>`.
            outputs (dict): Model outputs to populate with NPV results.

        Returns:
            None
        """
        io_meta_data = self.get_io_metadata()
        self.price_units = io_meta_data[f"sell_price_{self.output_txt}"]["units"]
        self.commodity_amount_units = self.commodity_sell_price_units.replace("USD/", "").strip(
            "()"
        )

        # compute rate_units from the price
        rate_units_from_price = _compute_rate_units(
            self.commodity_sell_price_units, check_conversion=False
        )
        rate_units_capacity = io_meta_data[f"rated_{self.options['commodity_type']}_production"][
            "units"
        ]
        conversion_ratio = convert_units(1, rate_units_from_price, rate_units_capacity)

        # ensure that sell price units are compatible with the rate units
        if float(conversion_ratio) != 1.0:
            # convert rate units to units compatible with the price_units
            inputs_adjusted = dict(inputs.items())
            capacity_converted = convert_units(
                inputs[f"rated_{self.options['commodity_type']}_production"],
                rate_units_capacity,
                rate_units_from_price,
            )
            inputs_adjusted[f"rated_{self.options['commodity_type']}_production"] = (
                capacity_converted
            )
            pf = self.populate_profast(inputs_adjusted)
        else:
            pf = self.populate_profast(inputs)

        outputs[f"NPV_{self.output_txt}"] = pf.cash_flow(
            price=inputs[f"sell_price_{self.output_txt}"][0]
        )
