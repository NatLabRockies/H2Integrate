from pathlib import Path

import numpy as np
import pandas as pd
import openmdao.api as om
import numpy_financial as npf
from attrs import field, define

from h2integrate.core.utilities import BaseConfig, check_plant_config_and_profast_params
from h2integrate.core.validators import gte_zero, range_val


@define(kw_only=True)
class NumpyFinancialNPVFinanceConfig(BaseConfig):
    """Configuration for NumpyFinancialNPVFinance.

    Attributes:
        plant_life (int): operating life of plant in years
        discount_rate (float): discount rate, expressed as a fraction between 0 and 1.
        commodity_sell_price (int | float, optional): sell price of commodity in
            USD/unit of commodity. Defaults to 0.0
        save_cost_breakdown (bool, optional): whether to save the cost breakdown per year.
            Defaults to False.
        save_npv_breakdown (bool, optional): whether to save the npv breakdown per technology.
            Defaults to False.
        cost_breakdown_file_description (str, optional): description to include in filename of
            cost breakdown file or npv breakdown file if either ``save_cost_breakdown`` or
            ``save_npv_breakdown`` is True. Defaults to 'default'.
    """

    plant_life: int = field(converter=int, validator=gte_zero)
    discount_rate: float = field(validator=range_val(0, 1))
    commodity_sell_price: int | float = field(default=0.0)
    save_cost_breakdown: bool = field(default=False)
    save_npv_breakdown: bool = field(default=False)
    cost_breakdown_file_description: str = field(default="default")


class NumpyFinancialNPV(om.ExplicitComponent):
    """OpenMDAO component for calculating Net Present Value (NPV)
    using the NumPy Financial.

    This component computes the NPV of a given commodity-producing plant over its
    operational lifetime, accounting for capital expenditures (CAPEX), operating
    expenditures (OPEX), refurbishment/replacement costs, and commodity revenues.

    NPV is calculated using the discount rate and plant life defined in the
    `plant_config`. By convention, investments (CAPEX, OPEX, refurbishment) are
    treated as negative cash flows, while revenues from commodity sales are
    positive. This follows the NumPy Financial convention:

    Reference:
        NumpPy Financial NPV documentation:
        https://numpy.org/numpy-financial/latest/npv.html#numpy_financial.npv

        By convention:
            - Investments or "deposits" are negative.
            - Income or "withdrawals" are positive.
            - Values typically start with the initial investment, so
              ``values[0]`` is often negative.

    Attributes:
        NPV_str (str): The dynamically generated name of the NPV output variable,
            based on `commodity_type` and optional `description`.
        tech_config (dict): Technology-specific configuration dictionary.
        config (NumpyFinancialNPVConfig): Parsed financial configuration parameters
            (e.g., discount rate, plant life, save options).
    """

    def initialize(self):
        self.options.declare("driver_config", types=dict)
        self.options.declare("plant_config", types=dict)
        self.options.declare("tech_config", types=dict)
        self.options.declare("commodity_type", types=str)
        self.options.declare("description", types=str, default="")

    def setup(self):
        commodity_type = self.options["commodity_type"]
        description = self.options["description"].strip() if "description" in self.options else ""

        # Use description only if non-empty
        suffix = f"_{description}" if description else ""

        self.NPV_str = f"NPV_{commodity_type}{suffix}"
        self.output_txt = f"{commodity_type}{suffix}"

        # TODO: update below with standardized naming
        if self.options["commodity_type"] == "electricity":
            commodity_units = "kW*h/year"
            commodity_price_units = "USD/(kW*h)"
        else:
            commodity_units = "kg/year"
            commodity_price_units = "USD/kg"

        self.add_output(self.NPV_str, val=0.0, units="USD")

        if self.options["commodity_type"] == "co2":
            self.add_input("co2_capture_kgpy", val=0.0, units="kg/year")
        else:
            self.add_input(
                f"total_{self.options['commodity_type']}_produced",
                val=0.0,
                units=commodity_units,
            )

        plant_config = self.options["plant_config"]
        finance_params = plant_config["finance_parameters"]["model_inputs"]
        if "plant_life" in finance_params:
            check_plant_config_and_profast_params(
                plant_config["plant"], finance_params, "plant_life", "plant_life"
            )
        finance_params.update({"plant_life": plant_config["plant"]["plant_life"]})

        self.config = NumpyFinancialNPVFinanceConfig.from_dict(finance_params)

        tech_config = self.tech_config = self.options["tech_config"]
        for tech in tech_config:
            self.add_input(f"capex_adjusted_{tech}", val=0.0, units="USD")
            self.add_input(f"opex_adjusted_{tech}", val=0.0, units="USD/year")
            self.add_input(
                f"varopex_adjusted_{tech}",
                val=0.0,
                shape=plant_config["plant"]["plant_life"],
                units="USD/year",
            )

        # TODO: update below with standardized naming
        if "electrolyzer" in tech_config:
            self.add_input("electrolyzer_time_until_replacement", units="h")

        self.add_input(
            f"sell_price_{self.output_txt}",
            val=self.config.commodity_sell_price,
            units=commodity_price_units,
        )

    def compute(self, inputs, outputs):
        """Compute the Net Present Value (NPV).

        Calculates discounted cash flows over the plant lifetime, accounting for:
            * Revenue from annual commodity production and sale.
            * CAPEX and OPEX for all technologies.
            * Replacement or refurbishment costs if provided.

        Optionally saves cost breakdowns and NPV breakdowns to CSV files if
        enabled in configuration.

        NPV that is positive indicates a profitable investment, while negative
        NPV indicates a loss.

        Args:
            inputs (dict-like): Dictionary of input values, including production,
                CAPEX, OPEX, and optional replacement periods.
            outputs (dict-like): Dictionary for storing computed outputs, including
                the NPV result.

        Produces:
            * `outputs[self.NPV_str]`: The total NPV in USD.

        Side Effects:
            * Writes annual cost breakdown and NPV breakdown CSVs to the configured
              output directory if `save_cost_breakdown` or `save_npv_breakdown`
              is enabled.

        Raises:
            FileNotFoundError: If the specified output directory cannot be created.
            ValueError: If refurbishment schedules cannot be derived from inputs.
        """
        # By convention in NPV calculations, investments (capex, opex, refurbishment) are
        # negative cash flows while revenues are positive. This follows the numpy_financial
        # convention where money going out is negative and money coming in is positive.
        sign_of_costs = -1

        # Extract annual production based on commodity type
        # CO2 uses different input naming convention than other commodities
        # TODO: update below for standardized naming and also variable simulation lengths
        if self.options["commodity_type"] != "co2":
            annual_production = float(inputs[f"total_{self.options['commodity_type']}_produced"][0])
        else:
            annual_production = float(inputs["co2_capture_kgpy"])

        # Calculate revenue from selling the commodity at the specified price
        # Revenue is only generated during operational years (not during construction year 0)
        income = inputs[f"sell_price_{self.output_txt}"][0] * annual_production
        # Create cash inflow array: [0 for year 0 (construction), income for years 1-N]
        cash_inflow = np.concatenate(([0], income * np.ones(self.config.plant_life)))

        # Initialize cost breakdown dictionary to track all cash flows by category
        # This will be used both for NPV calculation and optional CSV export
        cost_breakdown = {f"Cash Inflow of Selling {self.options['commodity_type']}": cash_inflow}

        # Track initial investment for reference (not currently used in calculations)
        initial_investment_cost = 0

        # Loop through each technology (e.g., wind, electrolyzer, etc.) to sum costs
        for tech in self.tech_config:
            # Extract financial inputs for this technology and apply negative sign convention
            capex = sign_of_costs * inputs[f"capex_adjusted_{tech}"][0]
            fixed_om = sign_of_costs * inputs[f"opex_adjusted_{tech}"][0]
            var_om = sign_of_costs * inputs[f"varopex_adjusted_{tech}"]

            # CAPEX occurs only in year 0 (construction phase)
            # Array size is plant_life+1 to include year 0
            capex_per_year = np.zeros(int(self.config.plant_life + 1))
            capex_per_year[0] = capex
            initial_investment_cost += capex

            # Store technology-specific costs in breakdown dictionary
            cost_breakdown[f"{tech}: capital cost"] = capex_per_year
            # Fixed O&M is constant each year during operation (years 1 through plant_life)
            cost_breakdown[f"{tech}: fixed o&m"] = np.concatenate(
                ([0], fixed_om * np.ones(self.config.plant_life))
            )
            # Variable O&M can vary by year based on utilization or other factors
            cost_breakdown[f"{tech}: variable o&m"] = np.concatenate(([0], var_om))

            # Retrieve technology-specific capital item parameters for refurbishment/replacement
            tech_capex_info = (
                self.tech_config[tech]["model_inputs"]
                .get("financial_parameters", {})
                .get("capital_items", {})
            )

            # Check if this technology requires periodic refurbishment or replacement
            # (e.g., electrolyzer stacks may need replacement every N years)
            if "replacement_cost_percent" in tech_capex_info:
                # Initialize array to track when replacements occur
                refurb_schedule = np.zeros(self.config.plant_life)

                # Find refurbishment period either from explicit config or calculated from hours
                if "refurbishment_period_years" in tech_capex_info:
                    refurb_period = tech_capex_info["refurbishment_period_years"]
                else:
                    # Calculate from hours until replacement (e.g., electrolyzer lifetime hours)
                    # Convert hours to years: divide by (24 hours/day * 365 days/year)
                    refurb_period = round(
                        float(inputs[f"{tech}_time_until_replacement"][0]) / (24 * 365)
                    )

                # Set replacement cost at regular intervals (every refurb_period years)
                # replacement_cost_percent is fraction of original CAPEX (e.g., 0.15 = 15%)
                refurb_schedule[refurb_period : self.config.plant_life : refurb_period] = (
                    tech_capex_info["replacement_cost_percent"]
                )

                # Calculate actual replacement costs by multiplying CAPEX by schedule percentages
                # capex is negative, so refurb_cost will also be negative (cash outflow)
                refurb_cost = capex * refurb_schedule
                # Add refurbishment schedule to cost breakdown
                cost_breakdown[f"{tech}: replacement cost"] = refurb_cost

        # Convert cost breakdown to list of arrays for aggregation (currently unused)
        total_costs = [np.array(v) for k, v in cost_breakdown.items()]
        np.array(total_costs).sum(axis=0)

        # Calculate NPV for each cost category and sum to get total NPV
        # This iterative approach also builds npv_cost_breakdown for optional reporting
        npv_item_check = 0
        npv_cost_breakdown = {}
        for cost_type, cost_vals in cost_breakdown.items():
            # Apply NPV formula: NPV = sum(cash_flow[t] / (1 + discount_rate)^t) for all t
            npv_item = npf.npv(self.config.discount_rate, cost_vals)
            npv_item_check += float(npv_item)
            npv_cost_breakdown[cost_type] = float(npv_item)

        # Store final NPV result in outputs
        outputs[self.NPV_str] = npv_item_check

        # Optionally save detailed breakdowns to CSV files for analysis
        if self.config.save_cost_breakdown or self.config.save_npv_breakdown:
            self._save_cost_breakdown_files(cost_breakdown, npv_cost_breakdown, npv_item_check)

    def _save_cost_breakdown_files(self, cost_breakdown, npv_cost_breakdown, total_npv):
        """Save cost breakdown and/or NPV breakdown to CSV files.

        Creates CSV files containing detailed breakdowns of costs and NPV calculations
        for post-processing analysis and reporting.

        Args:
            cost_breakdown (dict): Dictionary mapping cost categories to annual cost arrays.
                Keys are category names (e.g., "wind: capital cost"), values are numpy arrays
                of costs per year (length = plant_life + 1).
            npv_cost_breakdown (dict): Dictionary mapping cost categories to their NPV values.
                Keys are category names, values are floats representing discounted present value.
            total_npv (float): The total NPV summed across all categories in USD.

        File Formats:
            NPV breakdown CSV: Single column with cost category as index and NPV as value.
            Cost breakdown CSV: Rows are cost categories, columns are years (Year 0, Year 1, etc.).
        """
        # Set up output directory and ensure it exists
        output_dir = self.options["driver_config"]["general"]["folder_output"]
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Get file description for naming
        fdesc = self.config.cost_breakdown_file_description

        # Build base filename with appropriate commodity and description
        if (
            self.options["description"] == ""
            or self.options["description"] == self.options["commodity_type"]
        ):
            filename_base = f"{fdesc}_{self.options['commodity_type']}_NumpyFinancialNPV"
        else:
            # Extract description by removing NPV prefix and commodity type
            desc = (
                self.NPV_str.replace("NPV_", "")
                .replace(self.options["commodity_type"], "")
                .strip("_")
            )
            filename_base = f"{fdesc}_{self.options['commodity_type']}_{desc}_NumpyFinancialNPV"

        # Save NPV breakdown: single value per cost category
        if self.config.save_npv_breakdown:
            npv_fname = f"{filename_base}_NPV_breakdown.csv"
            npv_fpath = Path(output_dir) / npv_fname
            npv_breakdown = pd.Series(npv_cost_breakdown)
            npv_breakdown.loc["Total"] = total_npv
            npv_breakdown.name = "NPV (USD)"
            npv_breakdown.to_csv(npv_fpath)

        # Save annual cost breakdown: costs per year for each category
        if self.config.save_cost_breakdown:
            cost_fname = f"{filename_base}_cost_breakdown.csv"
            cost_fpath = Path(output_dir) / cost_fname

            # Create DataFrame with cost categories as rows and years as columns
            annual_cost_breakdown = pd.DataFrame(cost_breakdown).T
            # Add row totals (sum across all years for each category)
            annual_cost_breakdown["Total cost (USD)"] = annual_cost_breakdown.sum(axis=1)
            # Add column totals (sum across all categories for each year)
            annual_cost_breakdown.loc["Total cost per year (USD/year)"] = annual_cost_breakdown.sum(
                axis=0
            )
            # Rename columns to be more readable (0, 1, 2... -> Year 0, Year 1, Year 2...)
            new_colnames = {i: f"Year {i}" for i in annual_cost_breakdown.columns.to_list()}
            annual_cost_breakdown = annual_cost_breakdown.rename(columns=new_colnames)
            annual_cost_breakdown.to_csv(cost_fpath)
