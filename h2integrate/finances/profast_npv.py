from h2integrate.finances.profast_base import ProFastBase, _compute_price_units


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

        # Below is used so that commodity sell price units will be compatible
        # with the units of rated_commodity_production
        self.add_output(
            f"placeholder_{self.output_txt}",
            val=0.0,
            copy_units=f"rated_{self.options['commodity_type']}_production",
        )

        return

    def setup(self):
        """Set up inputs for the NPV calculation.

        Retrieves the commodity sell price from the plant configuration and registers it
        as an input for the component. Calls the base `setup()` method to initialize
        other ProFAST inputs and outputs.

        Raises:
            ValueError: If `commodity_sell_price` is not provided in the configuration.

        Returns:
            None
        """
        self.commodity_sell_price = self.options["plant_config"]["finance_parameters"][
            "model_inputs"
        ].get("commodity_sell_price", None)

        if self.commodity_sell_price is None:
            raise ValueError("commodity_sell_price is missing as an input")

        super().setup()

        self.add_input(
            f"sell_price_{self.output_txt}",
            val=self.commodity_sell_price,
            compute_units=_compute_price_units,
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
        self.commodity_amount_units = self.price_units.replace("USD/", "").strip("()")

        pf = self.populate_profast(inputs)

        outputs[f"NPV_{self.output_txt}"] = pf.cash_flow(
            price=inputs[f"sell_price_{self.output_txt}"][0]
        )
