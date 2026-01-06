import attrs
import numpy as np
import openmdao.api as om
from attrs import field, define

from h2integrate.core.utilities import (
    BaseConfig,
    attr_filter,
    attr_serializer,
    check_plant_config_and_profast_params,
)
from h2integrate.core.dict_utils import update_defaults
from h2integrate.core.validators import gt_zero, contains, gte_zero, range_val
from h2integrate.tools.profast_tools import create_years_of_operation, create_and_populate_profast


# Mapping between user-facing finance parameters and ProFAST internal parameter names
finance_to_pf_param_mapper = {
    # "income tax rate": "total income tax rate",
    "debt equity ratio": "debt equity ratio of initial financing",
    "discount rate": "leverage after tax nominal discount rate",
    "plant life": "operating life",
    "sales tax rate": "sales tax",
    "cash onhand months": "cash onhand",
    "topc": "TOPC",
    "installation time": "installation months",
    "inflation rate": "general inflation rate",
}


def format_params_for_profast_config(param_dict):
    """Format a parameter dictionary for BasicProFASTParameterConfig.

    This function standardizes dictionary key names so that top-level keys
    use underscores instead of spaces, while nested dictionary keys use spaces.

    Args:
        param_dict (dict): Input dictionary of financing parameters.

    Returns:
        dict: Reformatted dictionary compatible with BasicProFASTParameterConfig.
    """
    param_dict_reformatted = {}
    for k, v in param_dict.items():
        k_new = k.replace(" ", "_")  # Standardize top-level keys
        if isinstance(v, dict):
            # Convert nested dictionary keys to use spaces
            v_new = {vk.replace("_", " "): vv for vk, vv in v.items()}
            param_dict_reformatted[k_new] = v_new
        else:
            param_dict_reformatted[k_new] = v
    return param_dict_reformatted


def check_parameter_inputs(finance_params, plant_config):
    """Validate and format financing parameter inputs for ProFAST.

    This function:
      1. Detects duplicated keys that differ only by spaces or underscores.
      2. Ensures that synonymous parameters (e.g., "installation time" and
         "installation months") do not have conflicting values.
      3. Reformats the parameters for compatibility with ProFAST.

    Args:
        finance_params (dict): Financing parameters provided by the user.
        plant_config (dict): Plant configuration dictionary.

    Raises:
        ValueError: If duplicated keys are input.
        ValueError: If two equivalent keys have different values.

    Returns:
        dict: Validated and reformatted financing parameters for ProFAST.
    """
    # make consistent formatting for keys
    fin_params = {k.replace("_", " "): v for k, v in finance_params.items()}

    # check for duplicated entries differing only by underscores/spaces
    # (ex. 'analysis_start_year' and 'analysis start year')
    if len(fin_params) != len(finance_params):
        finance_keys = [k.replace("_", " ") for k, v in finance_params.items()]
        fin_keys = list(fin_params.keys())
        duplicated_entries = [k for k in fin_keys if finance_keys.count(k) > 1]
        # NOTE: not an issue if both values are the same,
        # but better to inform users earlier on to prevent accidents
        err_info = "\n".join(
            f"{d}: both `{d}` and `{d.replace('_','')}` map to {d}" for d in duplicated_entries
        )

        msg = f"Duplicate entries found in ProFastComp params. Duplicated entries are: {err_info}"
        raise ValueError(msg)

    # Check for conflicts between nickname/realname pairs
    # check if duplicate entries were input, like "installation time" AND "installation months"
    for nickname, realname in finance_to_pf_param_mapper.items():
        has_nickname = any(k == nickname for k, v in fin_params.items())
        has_realname = any(k == realname for k, v in fin_params.items())
        # check for duplicate entries
        if has_nickname and has_realname:
            check_plant_config_and_profast_params(fin_params, fin_params, nickname, realname)

    # Validate consistency between plant life and operating life
    if "operating life" in fin_params:
        check_plant_config_and_profast_params(
            plant_config["plant"], fin_params, "plant_life", "operating life"
        )

    # Re-map ProFAST parameters back to finance-style keys if needed
    if any(k in list(finance_to_pf_param_mapper.values()) for k, v in fin_params.items()):
        pf_param_to_finance_mapper = {v: k for k, v in finance_to_pf_param_mapper.items()}
        pf_params = {}
        for k, v in fin_params.items():
            if k.replace("_", " ") in pf_param_to_finance_mapper:
                pf_params[pf_param_to_finance_mapper[k]] = v
            else:
                pf_params[k] = v
        fin_params = dict(pf_params.items())

    # Final format for ProFAST configuration
    fin_params = format_params_for_profast_config(fin_params)
    fin_params.update({"plant_life": plant_config["plant"]["plant_life"]})

    return fin_params


@define(kw_only=True)
class BasicProFASTParameterConfig(BaseConfig):
    """Configuration class for financial parameters used in ProFAST models.

    This class defines default financing parameters, including discount rate,
    tax structure, inflation, and cost categories. Values are validated using
    range and type constraints.

    Attributes:
        plant_life (int): operating life of plant in years
        analysis_start_year (int): calendar year to start financial analysis
        installation_time (int): time between `analysis_start_year` and operation start in months
        discount_rate (float): leverage after tax nominal discount rate
        debt_equity_ratio (float): debt to equity ratio of initial financing.
        property_tax_and_insurance (float): property tax and insurance
        total_income_tax_rate (float): income tax rate
        capital_gains_tax_rate (float): tax rate fraction on capital gains
        sales_tax_rate (float): sales tax fraction
        debt_interest_rate (float): interest rate on debt
        inflation_rate (float): escalation rate. Set to zero for a nominal analysis.
        cash_onhand_months (int): number of months with cash onhand.
        admin_expense (float): administrative expense as a fraction of sales
        non_depr_assets (float, optional): cost (in `$`) of nondepreciable assets, such as land.
            Defaults to 0.
        end_of_proj_sale_non_depr_assets (float, optional): cost (in `$`) of nondepreciable assets
            that are sold at the end of the project. Defaults to 0.
        tax_loss_carry_forward_years (int, optional): Defaults to 0.
        tax_losses_monetized (bool, optional): Defaults to True.
        sell_undepreciated_cap (bool, optional): Defaults to True.
        credit_card_fees (float, optional): credit card fees as a fraction.
        demand_rampup (float, optional): Defaults to 0.
        debt_type (str, optional): must be either "Revolving debt" or "One time loan".
            Defaults to "Revolving debt".
        loan_period_if_used (int, optional): Loan period in years.
            Only used if `debt_type` is "One time loan". Defaults to 0.
        commodity (dict, optional):
        installation_cost  (dict, optional):
            - **value** (*float*): installation cost in USD. Defaults to 0.
            - **depr type** (*str*): either "Straight line" or "MACRS". Defaults to "Straight line"
            - **depr period** (*int*): depreciation period in years. Defaults to 4.
            - **depreciable** (*bool*): True if cost depreciates. Defaults to False.
        topc (dict, optional): take or pay contract.
        annual_operating_incentive (dict, optional):
        incidental_revenue (dict, optional):
        road_tax (dict, optional):
        labor (dict, optional):
        maintenance (dict, optional):
        rent (dict, optional):
        license_and_permit (dict, optional):
        one_time_cap_inct (dict, optional): investment tax credit.
    """

    # --- Primary finance parameters ---
    plant_life: int = field(converter=int, validator=gte_zero)
    analysis_start_year: int = field(converter=int, validator=range_val(1000, 4000))
    installation_time: int = field(converter=int, validator=gte_zero)

    discount_rate: float = field(validator=range_val(0, 1))
    debt_equity_ratio: float = field(validator=gt_zero)
    property_tax_and_insurance: float = field(validator=range_val(0, 1))

    total_income_tax_rate: float = field(validator=range_val(0, 1))
    capital_gains_tax_rate: float = field(validator=range_val(0, 1))
    sales_tax_rate: float = field(validator=range_val(0, 1))
    debt_interest_rate: float = field(validator=range_val(0, 1))

    inflation_rate: float = field(validator=range_val(0, 1))

    cash_onhand_months: int = field(converter=int)  # int?

    admin_expense: float = field(validator=range_val(0, 1))

    # --- Optional parameters ---
    non_depr_assets: float = field(default=0.0, validator=gte_zero)
    end_of_proj_sale_non_depr_assets: float = field(default=0.0, validator=gte_zero)

    tax_loss_carry_forward_years: int = field(default=0, validator=gte_zero)
    tax_losses_monetized: bool = field(default=True)
    sell_undepreciated_cap: bool = field(default=True)

    credit_card_fees: float = field(default=0.0)
    demand_rampup: float = field(default=0.0, validator=gte_zero)

    # --- Debt configuration ---
    debt_type: str = field(
        default="Revolving debt", validator=contains(["Revolving debt", "One time loan"])
    )
    loan_period_if_used: int = field(default=0, validator=gte_zero)

    # --- Nested dictionaries (financial categories) ---
    commodity: dict = field(
        default={
            "name": None,
            "unit": None,
            "initial price": 100,
            "escalation": 0.0,
        }
    )

    installation_cost: dict = field(
        default={
            "value": 0.0,
            "depr type": "Straight line",
            "depr period": 4,
            "depreciable": False,
        }
    )
    topc: dict = field(
        default={
            "unit price": 0.0,
            "decay": 0.0,
            "sunset years": 0,
            "support utilization": 0.0,
        }
    )

    annual_operating_incentive: dict = field(
        default={
            "value": 0.0,
            "decay": 0.0,
            "sunset years": 0,
            "taxable": True,
        }
    )
    incidental_revenue: dict = field(default={"value": 0.0, "escalation": 0.0})
    road_tax: dict = field(default={"value": 0.0, "escalation": 0.0})
    labor: dict = field(default={"value": 0.0, "rate": 0.0, "escalation": 0.0})
    maintenance: dict = field(default={"value": 0.0, "escalation": 0.0})
    rent: dict = field(default={"value": 0.0, "escalation": 0.0})
    license_and_permit: dict = field(default={"value": 0.0, "escalation": 0.0})
    one_time_cap_inct: dict = field(
        default={"value": 0.0, "depr type": "MACRS", "depr period": 3, "depreciable": False}
    )

    def as_dict(self) -> dict:
        """Return a dictionary formatted for ProFAST initialization.

        Converts the configuration to a ProFAST-compatible dictionary, replacing
        underscores with spaces, applying inflation defaults, and mapping keys
        to internal ProFAST parameter names.

        Returns:
            dict: Formatted parameter dictionary.
        """
        # Convert attrs object to serializable dict
        pf_params_init = attrs.asdict(self, filter=attr_filter, value_serializer=attr_serializer)

        # Rename underscores to spaces for ProFAST compatibility
        pf_params = {k.replace("_", " "): v for k, v in pf_params_init.items()}

        # Apply inflation rate defaults to escalation fields
        pf_params = update_defaults(pf_params, "escalation", self.inflation_rate)

        # Remap finance keys to ProFAST names where applicable
        params = {}
        for keyname, vals in pf_params.copy().items():
            if keyname in finance_to_pf_param_mapper:
                params[finance_to_pf_param_mapper[keyname]] = vals
            else:
                params[keyname] = vals
        return params


@define(kw_only=True)
class ProFASTDefaultCapitalItem(BaseConfig):
    """Default configuration for ProFAST capital cost items.

    Represents capital investment items such as equipment or infrastructure,
    with associated cost, depreciation, and sales tax options.

    Attributes:
        depr_period (int): depreciation period in years if using MACRS depreciation.
            Must be either 3, 5, 7, 10, 15 or 20.
        depr_type (str, optional): depreciation "MACRS" or "Straight line". Defaults to 'MACRS'.
        refurb (list[float], optional): Replacement schedule as a fraction of the capital cost.
            Defaults to [0.].
        replacement_cost_percent (float | int, optional): Replacement cost as a fraction of CapEx.
            Defaults to 0.0

    """

    depr_period: int = field(converter=int, validator=contains([3, 5, 7, 10, 15, 20]))
    depr_type: str = field(converter=str.strip, validator=contains(["MACRS", "Straight line"]))
    refurb: int | float | list[float] = field(default=[0.0])
    replacement_cost_percent: int | float = field(default=0.0, validator=range_val(0, 1))

    def create_dict(self):
        """Create a ProFAST-compatible dictionary of attributes.

        Excludes attributes not used by the ProFAST configuration file.

        Returns:
            dict: Dictionary containing ProFAST-compatible fields.
        """
        # Remove attributes not required by ProFAST input schema
        non_profast_attrs = ["replacement_cost_percent"]
        full_dict = self.as_dict()
        d = {k: v for k, v in full_dict.items() if k not in non_profast_attrs}
        return d


@define(kw_only=True)
class ProFASTDefaultFixedCost(BaseConfig):
    """Default configuration for ProFAST fixed operating costs.

    Represents recurring annual costs such as maintenance, rent, or insurance
    that do not vary with production level.

    Attributes:
        escalation (float | int, optional): annual escalation of price.
            Defaults to 0.
        unit (str): unit of the cost. Defaults to `$/year`.
        usage (float, optional): Usage multiplier, likely should be set to 1.
            Defaults to 1.0.
    """

    escalation: float | int = field()
    unit: str = field(default="$/year")
    usage: float | int = field(default=1.0)

    def create_dict(self):
        """Return a dictionary representation for ProFAST.

        Returns:
            dict: Dictionary of fixed cost attributes.
        """
        # Convert attributes to standard dictionary
        return self.as_dict()


@define(kw_only=True)
class ProFASTDefaultVariableCost(BaseConfig):
    """Default configuration for ProFAST variable costs.

    Represents costs that scale with production or feedstock usage.
    The total cost is calculated as ``usage * cost``.

    Attributes:
        escalation (float | int, optional): annual escalation of price.
            Defaults to 0.
        unit (str): unit of the cost, only used for reporting. The cost should be input in
            USD/unit of commodity.
        usage (float, optional): Usage of feedstock per unit of commodity.
            Defaults to 1.0.
    """

    escalation: float | int = field()
    unit: str = field()
    usage: float | int = field(default=1.0)

    def create_dict(self):
        """Return a dictionary representation for ProFAST.

        Returns:
            dict: Dictionary of variable cost attributes.
        """
        # Prepare dictionary for ProFAST configuration input
        return self.as_dict()


@define(kw_only=True)
class ProFASTDefaultCoproduct(BaseConfig):
    """Default configuration for ProFAST coproduct settings.

    Represents additional revenue sources or byproducts associated with
    the primary process. The total value is calculated as ``usage * cost``.

    Attributes:
        escalation (float | int, optional): annual escalation of price.
            Defaults to 0.
        unit (str): unit of the cost, only used for reporting. The cost should be input in
            USD/unit of commodity.
        usage (float, optional): Usage of feedstock per unit of commodity.
            Defaults to 1.0.
    """

    escalation: float | int = field()
    unit: str = field()
    usage: float | int = field(default=1.0)

    def create_dict(self):
        """Return a dictionary representation for ProFAST.

        Returns:
            dict: Dictionary of coproduct attributes.
        """
        # Prepare dictionary for ProFAST configuration input
        return self.as_dict()


@define(kw_only=True)
class ProFASTDefaultIncentive(BaseConfig):
    """Default configuration for ProFAST production-based incentives.

        Represents financial incentives (e.g., tax credits or subsidies)
        applied per unit of production over a defined period.

    Attributes:
        decay (float): rate of decay of incentive value.
            Recommended to set as -1*general inflation rate.
        sunset_years (int, optional): number of years incentive is active. Defaults to 10.
        tax_credit (bool, optional): Whether the incentive is a tax credit. Defaults to True.

    """

    decay: float | int = field()
    sunset_years: int = field(default=10, converter=int)
    tax_credit: bool = field(default=True)

    def create_dict(self):
        """Return a dictionary representation for ProFAST.

        Returns:
            dict: Dictionary of incentive attributes.
        """
        # Prepare dictionary for ProFAST configuration input
        return self.as_dict()


class ProFastBase(om.ExplicitComponent):
    """
    Base component for using the ProFAST financial model within OpenMDAO.

    This component aggregates capital, fixed, variable, and coproduct costs from
    user-defined technologies to compute financial metrics using ProFAST.

    Reference:
        ProFAST Documentation:
        https://www.nrel.gov/hydrogen/profast-access


    Attributes:
        tech_config (dict): Technology-specific model configurations included in the
            financial calculation.
        plant_config (dict): Plant configuration and financial parameter settings.
        driver_config (dict): Driver configuration parameters (not directly used in calculations).
        commodity_type (str): Type of commodity analyzed. Supported: 'hydrogen', 'electricity',
            'ammonia', 'nitrogen', and 'co2'.
        params (BasicProFASTParameterConfig): Financial parameters used in the ProFAST analysis.
        capital_item_settings (ProFASTDefaultCapitalItem): Default capital cost parameters.
        fixed_cost_settings (ProFASTDefaultFixedCost): Default fixed operating cost parameters.
        variable_cost_settings (ProFASTDefaultVariableCost): Default variable operating cost
            parameters.
        coproduct_cost_settings (ProFASTDefaultCoproduct): Default coproduct cost parameters.

    Inputs:
        capex_adjusted_{tech} (float): Adjusted capital expenditure for each
            user-defined technology, in USD.
        opex_adjusted_{tech} (float): Adjusted operational expenditure for each
            user-defined technology, in USD/year.
        total_{commodity}_produced (float): Total annual production of the selected commodity
            (units depend on commodity type).
        {tech}_time_until_replacement (float): Time until technology is replaced, in hours
            (currently only supported if "electrolyzer" is in tech_config).
        co2_capture_kgpy (float): Total annual CO2 captured, in kg/year
            (only for commodity_type "co2").

    Methods:
        initialize(): Declares component options.
        setup(): Defines inputs/outputs and initializes ProFAST configuration.
        populate_profast(inputs): Builds a ProFAST input dictionary based on user inputs.
        compute(inputs, outputs, ...): Must be implemented in a subclass.
    """

    def initialize(self):
        """Declare OpenMDAO component options."""
        self.options.declare("driver_config", types=dict)
        self.options.declare("plant_config", types=dict)
        self.options.declare("tech_config", types=dict)
        self.options.declare("commodity_type", types=str)
        self.options.declare("description", types=str, default="")

    def add_model_specific_outputs(self):
        """Placeholder for subclass-defined outputs."""
        raise NotImplementedError("This method should be implemented in a subclass.")

    def setup(self):
        """Set up component inputs and outputs based on plant and technology configurations."""
        # Determine commodity units
        if self.options["commodity_type"] == "electricity":
            commodity_units = "kW*h/year"
            self.price_units = "USD/(kW*h)"
        else:
            commodity_units = "kg/year"
            self.price_units = "USD/kg"

        # Construct output name based on commodity and optional description
        # this is necessary to allow for financial subgroups
        self.description = (
            f"_{self.options['description'].strip()}"
            if self.options["description"].strip() != ""
            else ""
        )
        self.output_txt = f"{self.options['commodity_type'].lower()}{self.description}"

        # Add model-specific outputs defined by subclass
        self.add_model_specific_outputs()

        # Add production input (CO2 capture or total commodity produced)
        if self.options["commodity_type"] == "co2":
            self.add_input("co2_capture_kgpy", val=0.0, units="kg/year", require_connection=True)
        else:
            self.add_input(
                f"total_{self.options['commodity_type']}_produced",
                val=-1.0,
                units=commodity_units,
                require_connection=True,
            )

        # Add inputs for CapEx, OpEx, and variable OpEx for each technology
        plant_life = int(self.options["plant_config"]["plant"]["plant_life"])
        tech_config = self.tech_config = self.options["tech_config"]
        for tech in tech_config:
            self.add_input(f"capex_adjusted_{tech}", val=0.0, units="USD")
            self.add_input(f"opex_adjusted_{tech}", val=0.0, units="USD/year")
            self.add_input(f"varopex_adjusted_{tech}", val=0.0, shape=plant_life, units="USD/year")

            # Include electrolyzer replacement time if applicable
            if tech.startswith("electrolyzer"):
                self.add_input(f"{tech}_time_until_replacement", units="h")

        # Load plant configuration and financial parameters
        plant_config = self.options["plant_config"]
        finance_params = plant_config["finance_parameters"]["model_inputs"]["params"]
        fin_params = check_parameter_inputs(finance_params, plant_config)

        # initialize financial parameters
        self.params = BasicProFASTParameterConfig.from_dict(fin_params)

        # initialize default capital item parameters
        capital_item_params = plant_config["finance_parameters"]["model_inputs"].get(
            "capital_items", {}
        )
        self.capital_item_settings = ProFASTDefaultCapitalItem.from_dict(capital_item_params)

        # initialize default fixed cost parameters
        fixed_cost_params = plant_config["finance_parameters"]["model_inputs"].get(
            "fixed_costs", {}
        )
        fixed_cost_params.setdefault("escalation", self.params.inflation_rate)
        self.fixed_cost_settings = ProFASTDefaultFixedCost.from_dict(fixed_cost_params)

        # initialize default variable cost parameters (same as feedstocks)
        variable_cost_params = plant_config["finance_parameters"]["model_inputs"].get(
            "variable_costs", {}
        )
        variable_cost_params.setdefault("escalation", self.params.inflation_rate)
        variable_cost_params.setdefault("unit", self.price_units.replace("USD", "$"))
        self.variable_cost_settings = ProFASTDefaultVariableCost.from_dict(variable_cost_params)

        # initialize default coproduct cost parameters (same as feedstocks)
        coproduct_cost_params = plant_config["finance_parameters"]["model_inputs"].get(
            "coproducts", {}
        )
        coproduct_cost_params.setdefault("escalation", self.params.inflation_rate)
        coproduct_cost_params.setdefault("unit", self.price_units.replace("USD", "$"))
        self.coproduct_cost_settings = ProFASTDefaultCoproduct.from_dict(coproduct_cost_params)

        # incentives - unused for now
        # incentive_params = plant_config["finance_parameters"]["model_inputs"].get(
        #     "incentives", {}
        # )
        # incentive_params.setdefault("decay", -1 * self.params.inflation_rate)
        # self.incentive_params_settings = ProFASTDefaultIncentive.from_dict(incentive_params)

    def populate_profast(self, inputs):
        """Populate and configure the ProFAST financial model for analysis.

        This is called during the `compute` method of the inheriting class.

        Args:
            inputs (dict): OpenMDAO input values for technology CapEx, OpEx, and production levels.

        Returns:
            ProFAST: A fully configured ProFAST financial model object ready for execution.
        """
        # determine commodity units
        mass_commodities = [
            "hydrogen",
            "ammonia",
            "co2",
            "nitrogen",
            "methanol",
            "iron_ore",
            "pig_iron",
        ]

        # create years of operation list
        years_of_operation = create_years_of_operation(
            self.params.plant_life,
            self.params.analysis_start_year,
            self.params.installation_time,
        )

        # update parameters with commodity, capacity, and utilization
        profast_params = self.params.as_dict()
        profast_params["commodity"].update({"name": self.options["commodity_type"]})
        profast_params["commodity"].update(
            {"unit": "kg" if self.options["commodity_type"] in mass_commodities else "kWh"}
        )

        # calculate capacity and total production based on commodity type
        if self.options["commodity_type"] != "co2":
            capacity = inputs[f"total_{self.options['commodity_type']}_produced"][0] / 365.0
            total_production = inputs[f"total_{self.options['commodity_type']}_produced"][0]
        else:
            capacity = inputs["co2_capture_kgpy"][0] / 365.0
            total_production = inputs["co2_capture_kgpy"][0]

        # define profast parameters for capacity and utilization
        profast_params["capacity"] = capacity  # TODO: update to actual daily capacity
        profast_params["long term utilization"] = 1  # TODO: update to capacity factor

        # initialize profast dictionary
        pf_dict = {"params": profast_params, "capital_items": {}, "fixed_costs": {}}

        # initialize dictionary of capital items and fixed costs
        capital_items = {}
        fixed_costs = {}
        variable_costs = {}
        coproduct_costs = {}

        # create default capital item and fixed cost entries
        capital_item_defaults = self.capital_item_settings.create_dict()
        fixed_cost_defaults = self.fixed_cost_settings.create_dict()
        variable_cost_defaults = self.variable_cost_settings.create_dict()
        coproduct_cost_defaults = self.coproduct_cost_settings.create_dict()

        # loop through technologies and create cost entries
        for tech in self.tech_config:
            # get tech-specific capital item parameters
            tech_model_inputs = self.tech_config[tech].get("model_inputs")
            if tech_model_inputs is None:
                continue  # Skip this tech if no model_inputs
            tech_capex_info = tech_model_inputs.get("financial_parameters", {}).get(
                "capital_items", {}
            )

            # add CapEx cost to tech-specific capital item entry
            tech_capex_info.update({"cost": float(inputs[f"capex_adjusted_{tech}"][0])})

            # see if any refurbishment information was input
            if "replacement_cost_percent" in tech_capex_info:
                refurb_schedule = np.zeros(self.params.plant_life)

                if "refurbishment_period_years" in tech_capex_info:
                    refurb_period = tech_capex_info["refurbishment_period_years"]
                else:
                    refurb_period = round(
                        float(inputs[f"{tech}_time_until_replacement"][0]) / (24 * 365)
                    )

                refurb_schedule[refurb_period : self.params.plant_life : refurb_period] = (
                    tech_capex_info["replacement_cost_percent"]
                )
                # add refurbishment schedule to tech-specific capital item entry
                tech_capex_info["refurb"] = list(refurb_schedule)

            # update any unset capital item parameters with the default values
            for cap_item_key, cap_item_val in capital_item_defaults.items():
                tech_capex_info.setdefault(cap_item_key, cap_item_val)
            capital_items[tech] = tech_capex_info

            # get tech-specific fixed cost parameters
            tech_opex_info = (
                self.tech_config[tech]["model_inputs"]
                .get("financial_parameters", {})
                .get("fixed_costs", {})
            )

            # add CapEx cost to tech-specific fixed cost entry
            tech_opex_info.update({"cost": float(inputs[f"opex_adjusted_{tech}"][0])})

            # update any unset fixed cost parameters with the default values
            for fix_cost_key, fix_cost_val in fixed_cost_defaults.items():
                tech_opex_info.setdefault(fix_cost_key, fix_cost_val)
            fixed_costs[tech] = tech_opex_info

            # get tech-specific variable cost parameters
            tech_varopex_info = (
                self.tech_config[tech]["model_inputs"]
                .get("financial_parameters", {})
                .get("variable_costs", {})
            )

            # add VarOpEx cost to tech-specific variable cost entry

            # if VarOpEx is positive, treat as a feedstock
            varopex_adjusted_tech = inputs[f"varopex_adjusted_{tech}"]

            if np.any(varopex_adjusted_tech >= 0):
                varopex_cost_per_unit_commodity = varopex_adjusted_tech / total_production
                varopex_dict = dict(zip(years_of_operation, varopex_cost_per_unit_commodity))
                tech_varopex_info.update({"cost": varopex_dict})

                # update any unset variable cost parameters with the default values
                for var_cost_key, var_cost_val in variable_cost_defaults.items():
                    tech_varopex_info.setdefault(var_cost_key, var_cost_val)
                variable_costs[tech] = tech_varopex_info

            # if VarOpEx is negative, treat as a coproduct
            else:
                tech_coproduct_info = (
                    self.tech_config[tech]["model_inputs"]
                    .get("financial_parameters", {})
                    .get("coproducts", {})
                )
                # make it positive
                coproduct_cost_per_unit_commodity = -1 * varopex_adjusted_tech / total_production
                coproduct_dict = dict(zip(years_of_operation, coproduct_cost_per_unit_commodity))
                tech_coproduct_info.update({"cost": coproduct_dict})

                # update any unset variable cost parameters with the default values
                for coprod_cost_key, coprod_cost_val in coproduct_cost_defaults.items():
                    tech_coproduct_info.setdefault(coprod_cost_key, coprod_cost_val)
                coproduct_costs[tech] = tech_coproduct_info

        # add capital costs and fixed costs to pf_dict
        pf_dict["capital_items"] = capital_items
        pf_dict["fixed_costs"] = fixed_costs
        pf_dict["feedstocks"] = variable_costs
        pf_dict["coproducts"] = coproduct_costs

        # create ProFAST object
        pf = create_and_populate_profast(pf_dict)
        return pf

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        """Placeholder for the OpenMDAO compute step."""
        raise NotImplementedError("This method should be implemented in a subclass.")
