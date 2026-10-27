import pytest
import openmdao.api as om
from pytest import approx, fixture

from h2integrate.converters.heat.shell_tube_hx_cost_model import ShellTubeHXCostModel


@fixture
def shell_tube_hx_cost_model_config():
    cost_parameters = {
        "cost_year": 2022,
        "hx_transfer_area": 100.0,
        "install_factor": 1.61,
        "material_factor": 1.0,
        "opex_percentage": 0.04,
    }

    tech_config = {
        "model_inputs": {
            "cost_parameters": cost_parameters,
        }
    }

    plant_config = {
        "plant": {
            "plant_life": 30,
            "simulation": {
                "n_timesteps": 8760,
                "dt": 3600,
            },
        }
    }
    return tech_config, plant_config


@pytest.mark.unit
class TestShellTubeHXCostModel:
    def _create_problem(self, config):
        prob = om.Problem()
        prob.model.add_subsystem(
            "shell_tube_hx_cost",
            ShellTubeHXCostModel(
                tech_config=config[0],
                plant_config=config[1],
                driver_config={},
            ),
            promotes=["*"],
        )
        prob.setup()
        return prob

    @staticmethod
    def _expected_capex(area_m2, install_factor, material_factor):
        # Sinnott & Towler (2021) u-tube shell-and-tube correlation, CEPCI 2010 -> 2022
        a, b, n = 28000.0, 54.0, 1.2
        cepci_scale = 816.0 / 532.9
        return (a + b * area_m2**n) * cepci_scale * install_factor * material_factor

    def test_hx_cost_calculation(self, shell_tube_hx_cost_model_config, subtests):
        prob = self._create_problem(shell_tube_hx_cost_model_config)
        prob.run_model()

        CapEx_USD = prob.get_val("shell_tube_hx_cost.CapEx", units="USD")
        OpEx_USD_per_year = prob.get_val("shell_tube_hx_cost.OpEx", units="USD/year")

        expected_CapEx_USD = self._expected_capex(100.0, 1.61, 1.0)
        expected_OpEx_USD_per_year = 0.04 * expected_CapEx_USD

        rel = 1e-6
        with subtests.test("CapEx"):
            assert CapEx_USD[0] == approx(expected_CapEx_USD, rel=rel)
        with subtests.test("OpEx"):
            assert OpEx_USD_per_year[0] == approx(expected_OpEx_USD_per_year, rel=rel)
        with subtests.test("cost_year"):
            assert prob.get_val("shell_tube_hx_cost.cost_year") == 2022

    def test_hx_cost_input_override(self, shell_tube_hx_cost_model_config, subtests):
        """Area and cost factors are OpenMDAO inputs and can be set/connected at runtime."""
        prob = self._create_problem(shell_tube_hx_cost_model_config)
        prob.set_val("hx_transfer_area", 250.0, units="m**2")
        prob.set_val("install_factor", 2.0)
        prob.set_val("material_factor", 1.3)
        prob.run_model()

        CapEx_USD = prob.get_val("shell_tube_hx_cost.CapEx", units="USD")
        OpEx_USD_per_year = prob.get_val("shell_tube_hx_cost.OpEx", units="USD/year")

        expected_CapEx_USD = self._expected_capex(250.0, 2.0, 1.3)

        rel = 1e-6
        with subtests.test("CapEx with overridden inputs"):
            assert CapEx_USD[0] == approx(expected_CapEx_USD, rel=rel)
        with subtests.test("OpEx with overridden inputs"):
            assert OpEx_USD_per_year[0] == approx(0.04 * expected_CapEx_USD, rel=rel)
