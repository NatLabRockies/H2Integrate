from attrs import field, define

from h2integrate.core.utilities import CostModelBaseConfig, merge_shared_inputs
from h2integrate.core.validators import contains, must_equal
from h2integrate.converters.hydrogen.electrolyzer_baseclass import ElectrolyzerCostBaseClass


@define(kw_only=True)
class SingliticoCostModelConfig(CostModelBaseConfig):
    """
    Configuration class for the ECOElectrolyzerPerformanceModel, outputs costs in 2021 USD.

    Args:
        location (str): The location of the electrolyzer; options include "onshore" or "offshore".
        electrolyzer_capex (int): $/kW overnight installed capital costs for a 1 MW system in
            2022 USD/kW (DOE hydrogen program record 24005 Clean Hydrogen Production Cost Scenarios
            with PEM Electrolyzer Technology 05/20/24) #TODO: convert to refs
            (https://www.hydrogen.energy.gov/docs/hydrogenprogramlibraries/pdfs/24005-clean-hydrogen-production-cost-pem-electrolyzer.pdf?sfvrsn=8cb10889_1)
    """

    location: str = field(validator=contains(["onshore", "offshore"]))
    electrolyzer_capex: int = field()
    cost_year: int = field(default=2021, converter=int, validator=must_equal(2021))


class SingliticoCostModel(ElectrolyzerCostBaseClass):
    """
    An OpenMDAO component that computes the cost of a PEM electrolyzer.
    """

    def setup(self):
        self.config = SingliticoCostModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost")
        )

        super().setup()

        self.add_input(
            "electrolyzer_size_mw",
            val=0,
            units="MW",
            desc="Size of the electrolyzer in MW",
        )

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        electrolyzer_size_mw = float(inputs["electrolyzer_size_mw"][0])

        # run hydrogen production cost model - from hopp examples
        if self.config.location == "onshore":
            elec_location = 0
        else:
            elec_location = 1

        P_elec = electrolyzer_size_mw * 1e-3  # [GW]
        RC_elec = self.config.electrolyzer_capex  # [USD/kW]

        # PEM costs based on Singlitico et al. 2021
        # Values for CapEX & OpEx taken from paper, Table B.2, PEMEL.
        # Installation costs include land, contingency, contractors, legal fees, construction,
        # engineering, yard improvements, buildings, electrics, piping, instrumentation,
        # and installation and grid connection.
        IF = 0.33  # installation fraction [% RC_elec]
        RP_elec = 10  # reference power [MW]

        # Choose the scale factor based on electrolyzer size
        if P_elec < 10 / 10**3:
            SF_elec = -0.21  # scale factor, -0.21 for <10MW, -0.14 for >10MW
        else:
            SF_elec = -0.14  # scale factor, -0.21 for <10MW, -0.14 for >10MW

        # If electrolyzer capacity is >100MW, fix unit cost to 100MW electrolyzer as economies of
        # scale stop at sizes above this, according to assumption in paper.
        if P_elec > 100 / 10**3:
            P_elec_cost_per_unit_calc = 0.1
        else:
            P_elec_cost_per_unit_calc = P_elec

        # Calculate CapEx for a single electrolyzer
        # Return the cost of a single electrolyzer of the specified capacity in millions of USD
        # MUSD = GW   * MUSD/GW *      -       *    GW   * MW/GW /      MW       **      -
        capex_musd = (
            P_elec_cost_per_unit_calc
            * RC_elec
            * (1 + IF * elec_location)
            * ((P_elec_cost_per_unit_calc * 10**3 / RP_elec) ** SF_elec)
        )
        capex_per_unit = capex_musd / P_elec_cost_per_unit_calc
        electrolyzer_capital_cost_musd = capex_per_unit * P_elec

        # Calculate OpEx for a single electrolyzer
        # If electrolyzer capacity is >100MW, fix unit cost to 100MW electrolyzer
        P_elec_opex = P_elec
        if P_elec > 100 / 10**3:
            P_elec_opex = 0.1

        # Including material cost for planned and unplanned maintenance, labor cost in central
        # Europe, which all depend on a system scale. Excluding the cost of electricity and the
        # stack replacement, calculated separately.
        # MUSD*MW         MUSD    *              -                *    -   *    GW   * MW/GW
        opex_elec_eq = (
            electrolyzer_capital_cost_musd
            * (1 - IF * (1 + elec_location))
            * 0.0344
            * (P_elec_opex * 10**3) ** -0.155
        )

        # Covers the other operational expenditure related to the facility level. This includes site
        # management, land rent and taxes, administrative fees (insurance, legal fees...), and site
        # maintenance.
        # MUSD                    MUSD
        opex_elec_neq = 0.04 * electrolyzer_capital_cost_musd * IF * (1 + elec_location)

        electrolyzer_om_cost_musd = opex_elec_eq + opex_elec_neq

        # Convert from M USD to USD
        electrolyzer_total_capital_cost = electrolyzer_capital_cost_musd * 1e6
        electrolyzer_OM_cost = electrolyzer_om_cost_musd * 1e6

        outputs["CapEx"] = electrolyzer_total_capital_cost
        outputs["OpEx"] = electrolyzer_OM_cost
