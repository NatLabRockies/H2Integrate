import numpy as np
import openmdao.api as om
from pytest import approx

from h2integrate.converters.hydrogen.singlitico_cost_model import SingliticoCostModel


TOL = 1e-3

BASELINE = np.array(
    [
        # onshore, [capex, opex]
        [
            [50.7105172052493, 1.2418205567631722],
        ],
        # offshore, [capex, opex]
        [
            [67.44498788298158, 2.16690312809502],
        ],
    ]
)


class TestSingliticoCostModel:
    P_elec_mw = 100.0  # [MW]
    RC_elec = 700  # [USD/kW]

    def _create_problem(self, location):
        """Helper method to create and set up an OpenMDAO problem."""
        prob = om.Problem()
        prob.model.add_subsystem(
            "singlitico_cost_model",
            SingliticoCostModel(
                plant_config={
                    "plant": {
                        "plant_life": 30,
                        "simulation": {
                            "n_timesteps": 8760,
                        },
                    },
                },
                tech_config={
                    "model_inputs": {
                        "cost_parameters": {
                            "location": location,
                            "electrolyzer_capex": self.RC_elec,
                        },
                    }
                },
            ),
            promotes=["*"],
        )
        prob.setup()
        prob.set_val("electrolyzer_size_mw", self.P_elec_mw, units="MW")
        prob.set_val("electricity_in", np.ones(8760) * self.P_elec_mw, units="kW")
        prob.set_val("total_hydrogen_produced", 1000.0, units="kg/year")
        return prob

    def test_calc_capex_onshore(self):
        prob = self._create_problem("onshore")
        prob.run_model()

        capex_musd = prob["CapEx"] / 1e6
        assert capex_musd == approx(BASELINE[0][0][0], TOL)

    def test_calc_capex_offshore(self):
        prob = self._create_problem("offshore")
        prob.run_model()

        capex_musd = prob["CapEx"] / 1e6
        assert capex_musd == approx(BASELINE[1][0][0], TOL)

    def test_calc_opex_onshore(self):
        prob = self._create_problem("onshore")
        prob.run_model()

        opex_musd = prob["OpEx"] / 1e6
        assert opex_musd == approx(BASELINE[0][0][1], TOL)

    def test_calc_opex_offshore(self):
        prob = self._create_problem("offshore")
        prob.run_model()

        opex_musd = prob["OpEx"] / 1e6
        assert opex_musd == approx(BASELINE[1][0][1], TOL)

    def test_run_onshore(self):
        prob = self._create_problem("onshore")
        prob.run_model()

        capex_musd = prob["CapEx"] / 1e6
        opex_musd = prob["OpEx"] / 1e6

        assert capex_musd == approx(BASELINE[0][0][0], TOL)
        assert opex_musd == approx(BASELINE[0][0][1], TOL)

    def test_run_offshore(self):
        prob = self._create_problem("offshore")
        prob.run_model()

        capex_musd = prob["CapEx"] / 1e6
        opex_musd = prob["OpEx"] / 1e6

        assert capex_musd == approx(BASELINE[1][0][0], TOL)
        assert opex_musd == approx(BASELINE[1][0][1], TOL)


if __name__ == "__main__":
    test_set = TestSingliticoCostModel()
