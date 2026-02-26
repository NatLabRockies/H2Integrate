from pathlib import Path

import numpy as np

from h2integrate.core.utilities import dict_to_yaml_formatting
from h2integrate.tools.profast_tools import (
    run_profast,
    convert_pf_to_dict,
    make_price_breakdown,
    format_profast_price_breakdown_per_year,
)
from h2integrate.finances.profast_base import ProFastBase
from h2integrate.core.inputs.validation import write_yaml


class ProFastLCO(ProFastBase):
    """Calculates the Levelized Cost of Commodity (LCO) using ProFAST for a given technology
    configuration.

    This component estimates the levelized cost of user-defined commodities—such as hydrogen (LCOH),
    electricity (LCOE), ammonia (LCOA), nitrogen (LCON), or CO₂ (LCOC)—based on the technologies
    included in the configuration. It can output both scalar results (e.g., LCO, IRR, WACC) and
    detailed cost breakdowns. Optionally, ProFAST inputs, configurations, and results can be
    exported to YAML and CSV files for record-keeping or debugging.

    Attributes:
        LCO_str (str): Name of the primary output variable (e.g., "LCOH").
        output_txt (str): Text label used for output naming, typically based on the commodity type.
        outputs_to_units (dict): Mapping of output variable names to their physical units.
        lco_units (str): Units of the LCO output, dependent on the commodity type (e.g., USD/kg or
            USD/kWh).

    Outputs:
        LCOx (float): Levelized cost of the commodity, where `x` corresponds to the first letter of
            the commodity (e.g., LCOH for hydrogen). Units depend on commodity type.
        wacc_<commodity> (float): Weighted average cost of capital, as a fraction.
        crf_<commodity> (float): Capital recovery factor, as a fraction.
        irr_<commodity> (float): Internal rate of return, as a fraction.
        profit_index_<commodity> (float): Profitability index, dimensionless.
        investor_payback_period_<commodity> (float): Time until the initial investment is
            recovered (years).
        price_<commodity> (float): First-year selling price of the commodity in the same units
            as LCOx.
        <LCOx>_breakdown (dict): Annualized breakdown of LCO costs by category.

    Methods:
        add_model_specific_outputs():
            Creates model outputs for the LCO and associated financial metrics, including
                cost breakdowns.

        compute(inputs, outputs, discrete_inputs, discrete_outputs):
            Runs the ProFAST simulation, calculates the LCO and financial outputs, generates
            breakdowns, and optionally exports configuration and results to files.

    Notes:
        - The outputs and file exports are governed by user-specified finance parameters in the
          plant configuration.
        - The computation relies on `run_profast()` for core financial simulation and
          `make_price_breakdown()` for cost disaggregation.
    """

    def add_model_specific_outputs(self):
        """Define output variables specific to the selected commodity.

        Constructs standardized names for the Levelized Cost of Commodity (LCO) and its
        associated financial metrics (WACC, CRF, IRR, etc.), based on the commodity type
        and optional user-specified description.

        Returns:
            None
        """
        # Construct output name based on commodity and optional description
        # this is necessary to allow for financial subgroups
        desc = self.options["description"].strip().strip("_()-")
        base = f"LCO{self.options['commodity_type'][0].upper()}"
        self.LCO_str = f"{base}_{desc}" if desc else base

        self.add_output(self.LCO_str, val=0.0, units=self.price_units)
        self.outputs_to_units = {
            "wacc": "percent",
            "crf": "percent",
            "irr": "percent",
            "profit_index": "unitless",
            "investor_payback_period": "yr",
            "price": self.price_units,
        }
        for output_var, units in self.outputs_to_units.items():
            self.add_output(f"{output_var}_{self.output_txt}", val=0.0, units=units)

        self.add_discrete_output(f"{self.LCO_str}_breakdown", val={}, desc="LCO Breakdown of costs")
        return

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        """Run ProFAST simulation and populate outputs.

        Executes a ProFAST financial simulation using model inputs to calculate the
        Levelized Cost of Commodity (LCO) and related economic metrics. Generates cost
        breakdown dictionaries and optionally exports configuration and results to YAML
        or CSV files, depending on user options.

        Args:
            inputs (dict): Continuous model inputs.
            outputs (dict): Continuous model outputs to be populated.
            discrete_inputs (dict): Discrete model inputs (e.g., configuration flags).
            discrete_outputs (dict): Discrete outputs for structured results.

        Returns:
            None
        """
        pf = self.populate_profast(inputs)

        # simulate ProFAST
        sol, summary, price_breakdown = run_profast(pf)

        # populate outputs
        # Output names based on naming convention for finance subgroups
        outputs[self.LCO_str] = sol["lco"]
        for output_var in self.outputs_to_units.keys():
            val = sol[output_var.replace("_", " ")]
            if isinstance(val, np.ndarray | list | tuple):  # only for IRR
                # if len(val)>0:
                val = val[-1]
            outputs[f"{output_var}_{self.output_txt}"] = val

        # make dictionary of ProFAST config
        pf_config_dict = convert_pf_to_dict(pf)

        # make LCO cost breakdown
        lco_breakdown, lco_check = make_price_breakdown(price_breakdown, pf_config_dict)
        discrete_outputs[f"{self.LCO_str}_breakdown"] = lco_breakdown

        # Check whether to export profast object to .yaml file
        save_results = self.options["plant_config"]["finance_parameters"]["model_inputs"].get(
            "save_profast_results", False
        )
        save_config = self.options["plant_config"]["finance_parameters"]["model_inputs"].get(
            "save_profast_config", False
        )

        if save_results or save_config:
            output_dir = self.options["driver_config"]["general"]["folder_output"]
            fdesc = self.options["plant_config"]["finance_parameters"]["model_inputs"].get(
                "profast_output_description", "ProFastLCO"
            )

            fbasename = f"{fdesc}_{self.output_txt}"

            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

            pf_config_dict = dict_to_yaml_formatting(pf_config_dict)

            if save_config:
                config_fpath = Path(output_dir) / f"{fbasename}_config.yaml"
                write_yaml(pf_config_dict, config_fpath)

            if save_results:
                price_breakdown_formatted = format_profast_price_breakdown_per_year(price_breakdown)
                pf_breakdown_fpath = Path(output_dir) / f"{fbasename}_profast_price_breakdown.csv"
                lco_breakdown_fpath = Path(output_dir) / f"{fbasename}_LCO_breakdown.yaml"
                price_breakdown_formatted.to_csv(pf_breakdown_fpath)
                lco_breakdown = dict_to_yaml_formatting(lco_breakdown)
                write_yaml(lco_breakdown, lco_breakdown_fpath)
