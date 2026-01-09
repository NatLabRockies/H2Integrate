import pyomo.environ as pyo
from pyomo.network import Arc


# from h2integrate.control.control_rules.pyomo_rule_baseclass import PyomoRuleBaseClass


# @define
# class PyomoDispatchGenericConverterMinOperatingCostsConfig(PyomoRuleBaseConfig):
#     """
#     Configuration class for the PyomoDispatchGenericConverterMinOperatingCostsConfig.

#     This class defines the parameters required to configure the `PyomoRuleBaseConfig`.

#     Attributes:
#         commodity_cost_per_production (float): cost of the commodity per production (in $/kWh).
#     """

#     commodity_cost_per_production: str = field()


class PyomoDispatchPlantRule:
    def __init__(
        self,
        pyomo_model: pyo.ConcreteModel,
        index_set: pyo.Set,
        source_techs: list,
        tech_dispatch_models: pyo.ConcreteModel,
        dispatch_options: dict,
        block_set_name: str = "hybrid",
    ):
        # self.config = PyomoDispatchGenericConverterMinOperatingCostsConfig.from_dict(
        #     self.options["tech_config"]["model_inputs"]["dispatch_rule_parameters"]
        # )

        self.source_techs = source_techs  # self.pyomo_model
        self.options = dispatch_options  # only using dispatch_options.time_weighting_factor
        self.power_source_gen_vars = {key: [] for key in index_set}
        self.tech_dispatch_models = tech_dispatch_models
        self.load_vars = {key: [] for key in index_set}
        self.ports = {key: [] for key in index_set}
        self.arcs = []

        self.round_digits = 4

        self.model = pyomo_model
        self.blocks = pyo.Block(index_set, rule=self.dispatch_block_rule)

        self.model.__setattr__(block_set_name, self.blocks)

    def dispatch_block_rule(self, hybrid, t):
        ##################################
        # Parameters                     #
        ##################################
        self._create_parameters(hybrid)
        ##################################
        # Variables / Ports              #
        ##################################
        self._create_variables_and_ports(hybrid, t)
        ##################################
        # Constraints                    #
        ##################################
        self._create_hybrid_constraints(hybrid, t)

    def initialize_parameters(
        self, commodity_in: list, commodity_demand: list, dispatch_params: dict
    ):
        """Initialize parameters method."""
        self.time_weighting_factor = self.options.time_weighting_factor  # Discount factor
        for tech in self.source_techs:
            pyomo_block = self.tech_dispatch_models.__getattribute__(f"{tech}_rule")
            pyomo_block.initialize_parameters(commodity_in, commodity_demand, dispatch_params)

    def _create_variables_and_ports(self, hybrid, t):
        for tech in self.source_techs:
            pyomo_block = self.tech_dispatch_models.__getattribute__(f"{tech}_rule")
            gen_var, load_var = pyomo_block._create_hybrid_variables(hybrid, f"{tech}_rule")

            self.power_source_gen_vars[t].append(gen_var)
            self.load_vars[t].append(load_var)
            self.ports[t].append(pyomo_block._create_hybrid_port(hybrid, f"{tech}_rule"))

    @staticmethod
    def _create_parameters(hybrid):
        hybrid.time_weighting_factor = pyo.Param(
            doc="Exponential time weighting factor [-]",
            initialize=1.0,
            within=pyo.PercentFraction,
            mutable=True,
            units=pyo.units.dimensionless,
        )

    def _create_hybrid_constraints(self, hybrid, t):
        hybrid.production_total = pyo.Constraint(
            doc="hybrid system generation total",
            rule=hybrid.system_production == sum(self.power_source_gen_vars[t]),
        )

        hybrid.load_total = pyo.Constraint(
            doc="hybrid system load total",
            rule=hybrid.system_load == sum(self.load_vars[t]),
        )

    def create_arcs(self):
        # Defining the mapping between battery to system level
        #
        ##################################
        # Arcs                           #
        ##################################
        for tech in self.source_techs:
            pyomo_block = self.tech_dispatch_models.__getattribute__(f"{tech}_rule")

            def arc_rule(m, t):
                source_port = pyomo_block.blocks[t].port
                destination_port = self.blocks[t].__getattribute__(f"{tech}_rule_port")
                return {"source": source_port, "destination": destination_port}

            tech_hybrid_arc = Arc(self.blocks.index_set(), rule=arc_rule)
            self.model.__setattr__(f"{tech}_hybrid_arc", tech_hybrid_arc)

            tech_arc = self.model.__getattribute__(f"{tech}_hybrid_arc")
            self.arcs.append(tech_arc)

        pyo.TransformationFactory("network.expand_arcs").apply_to(self.model)

    def update_time_series_parameters(
        self, start_time: int, commodity_in=list, commodity_demand=list
    ):
        for tech in self.source_techs:
            name = tech + "_rule"
            pyomo_block = self.tech_dispatch_models.__getattribute__(name)
            pyomo_block.update_time_series_parameters(start_time, commodity_in, commodity_demand)

    def create_min_operating_cost_expression(self):
        self._delete_objective()

        def operating_cost_objective_rule(m) -> float:
            obj = 0.0
            for tech in self.source_techs:
                name = tech + "_rule"
                print("Obj function", name)
                # Create the min_operating_cost expression for each technology
                pyomo_block = self.tech_dispatch_models.__getattribute__(name)
                # Add to the overall hybrid operating cost expression
                obj += pyomo_block.min_operating_cost_objective(self.blocks, name)
            return obj

        # Set operating cost rule in Pyomo problem objective
        self.model.objective = pyo.Objective(rule=operating_cost_objective_rule, sense=pyo.minimize)

    def _delete_objective(self):
        if hasattr(self.model, "objective"):
            self.model.del_component(self.model.objective)

    # def get_block_value(self, var_name):
    #     return [self.blocks[t].__getattribute__(var_name).value for t in self.blocks.index_set()]

    # @property
    # def blocks(self) -> pyo.Block:
    #     return self._blocks

    # @property
    # def model(self) -> pyo.ConcreteModel:
    #     return self._model

    @property
    def time_weighting_factor(self) -> float:
        for t in self.blocks.index_set():
            return self.blocks[t + 1].time_weighting_factor.value

    @time_weighting_factor.setter
    def time_weighting_factor(self, weighting: float):
        for t in self.blocks.index_set():
            self.blocks[t].time_weighting_factor = round(weighting**t, self.round_digits)

    # @property
    # def time_weighting_factor_list(self) -> list:
    #     return [self.blocks[t].time_weighting_factor.value for t in self.blocks.index_set()]

    # Outputs

    # @property
    # def objective_value(self):
    #     return pyo.value(self.model.objective)

    # @property
    # def get_production_value(self, tech_name, commodity_name):
    #     return f"{tech_name}_{commodity_name}"

    # @property
    # def charge_commodity(self) -> list:
    #     val = self.get_block_value("charge_commodity")
    #     # below returns a lit of length 24 for 24 hours/timesteps
    #     return val #[self.blocks[t].charge_commodity.value for t in self.blocks.index_set()]

    # @property
    # def discharge_commodity(self) -> list:
    #     return [self.blocks[t].discharge_commodity.value for t in self.blocks.index_set()]

    # @property
    # def system_production(self) -> list:
    #     return [self.blocks[t].system_production.value for t in self.blocks.index_set()]

    # @property
    # def system_load(self) -> list:
    #     return [self.blocks[t].system_load.value for t in self.blocks.index_set()]

    @property
    def storage_commodity_out(self) -> list:
        # THIS IS USED
        """Storage commodity out."""
        return [
            self.blocks[t].discharge_commodity.value - self.blocks[t].charge_commodity.value
            for t in self.blocks.index_set()
        ]

    # @property
    # def electricity_sales(self) -> list:
    #     if "grid" in self.power_sources:
    #         tb = self.power_sources["grid"].dispatch.blocks
    #         return [
    #             tb[t].time_duration.value
    #             * tb[t].electricity_sell_price.value
    #             * self.blocks[t].electricity_sold.value
    #             for t in self.blocks.index_set()
    #         ]

    # @property
    # def electricity_purchases(self) -> list:
    #     if "grid" in self.power_sources:
    #         tb = self.power_sources["grid"].dispatch.blocks
    #         return [
    #             tb[t].time_duration.value
    #             * tb[t].electricity_purchase_price.value
    #             * self.blocks[t].electricity_purchased.value
    #             for t in self.blocks.index_set()
    #         ]
