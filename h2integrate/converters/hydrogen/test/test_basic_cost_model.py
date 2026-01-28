import numpy as np
import openmdao.api as om
from pytest import approx

from h2integrate.converters.hydrogen.basic_cost_model import BasicElectrolyzerCostModel


class TestBasicH2Costs:
    electrolyzer_size_mw = 100
    h2_annual_output = 500
    nturbines = 10
    n_timesteps = 500
    electrical_generation_timeseries = (
        electrolyzer_size_mw * (np.sin(range(0, n_timesteps))) * 0.5 + electrolyzer_size_mw * 0.5
    )

    per_turb_electrolyzer_size_mw = electrolyzer_size_mw / nturbines
    per_turb_h2_annual_output = h2_annual_output / nturbines
    per_turb_electrical_generation_timeseries = electrical_generation_timeseries / nturbines

    elec_capex = 600  # $/kW
    time_between_replacement = 80000  # hours
    useful_life = 30  # years

    def _create_problem(self, location, electrolyzer_size_mw, electrical_generation_timeseries):
        """Helper method to create and set up an OpenMDAO problem."""
        prob = om.Problem()
        prob.model.add_subsystem(
            "basic_cost_model",
            BasicElectrolyzerCostModel(
                plant_config={
                    "plant": {
                        "plant_life": self.useful_life,
                        "simulation": {
                            "n_timesteps": self.n_timesteps,
                        },
                    },
                },
                tech_config={
                    "model_inputs": {
                        "cost_parameters": {
                            "location": location,
                            "electrolyzer_capex": self.elec_capex,
                            "time_between_replacement": self.time_between_replacement,
                        },
                    }
                },
            ),
            promotes=["*"],
        )
        prob.setup()
        prob.set_val("electricity_in", electrical_generation_timeseries, units="kW")
        prob.set_val("electrolyzer_size_mw", electrolyzer_size_mw, units="MW")
        return prob

    def test_on_turbine_capex(self):
        prob = self._create_problem(
            "offshore",
            self.per_turb_electrolyzer_size_mw,
            self.per_turb_electrical_generation_timeseries,
        )
        prob.set_val("total_hydrogen_produced", self.per_turb_h2_annual_output, units="kg/year")
        prob.run_model()

        per_turb_electrolyzer_total_capital_cost = prob["CapEx"]
        electrolyzer_total_capital_cost = per_turb_electrolyzer_total_capital_cost * self.nturbines

        assert electrolyzer_total_capital_cost == approx(127698560.0)

    def test_on_platform_capex(self):
        prob = self._create_problem(
            "offshore", self.electrolyzer_size_mw, self.electrical_generation_timeseries
        )
        prob.set_val("total_hydrogen_produced", self.h2_annual_output, units="kg/year")
        prob.run_model()

        electrolyzer_total_capital_cost = prob["CapEx"]

        assert electrolyzer_total_capital_cost == approx(125448560.0)

    def test_on_land_capex(self):
        prob = self._create_problem(
            "onshore",
            self.per_turb_electrolyzer_size_mw,
            self.per_turb_electrical_generation_timeseries,
        )
        prob.set_val("total_hydrogen_produced", self.per_turb_h2_annual_output, units="kg/year")
        prob.run_model()

        per_turb_electrolyzer_total_capital_cost = prob["CapEx"]
        electrolyzer_total_capital_cost = per_turb_electrolyzer_total_capital_cost * self.nturbines

        assert electrolyzer_total_capital_cost == approx(116077280.00000003)

    def test_on_turbine_opex(self):
        prob = self._create_problem(
            "offshore",
            self.per_turb_electrolyzer_size_mw,
            self.per_turb_electrical_generation_timeseries,
        )
        prob.set_val("total_hydrogen_produced", self.per_turb_h2_annual_output, units="kg/year")
        prob.run_model()

        per_turb_electrolyzer_OM_cost = prob["OpEx"]
        electrolyzer_OM_cost = per_turb_electrolyzer_OM_cost * self.nturbines

        assert electrolyzer_OM_cost == approx(1377207.4599629682)

    def test_on_platform_opex(self):
        prob = self._create_problem(
            "offshore", self.electrolyzer_size_mw, self.electrical_generation_timeseries
        )
        prob.set_val("total_hydrogen_produced", self.h2_annual_output, units="kg/year")
        prob.run_model()

        electrolyzer_OM_cost = prob["OpEx"]

        assert electrolyzer_OM_cost == approx(1864249.9310054395)

    def test_on_land_opex(self):
        prob = self._create_problem(
            "onshore",
            self.per_turb_electrolyzer_size_mw,
            self.per_turb_electrical_generation_timeseries,
        )
        prob.set_val("total_hydrogen_produced", self.per_turb_h2_annual_output, units="kg/year")
        prob.run_model()

        per_turb_electrolyzer_OM_cost = prob["OpEx"]
        electrolyzer_OM_cost = per_turb_electrolyzer_OM_cost * self.nturbines

        assert electrolyzer_OM_cost == approx(1254447.4599629682)


if __name__ == "__main__":
    test_set = TestBasicH2Costs()
