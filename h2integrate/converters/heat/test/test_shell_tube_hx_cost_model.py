import openmdao.api as om
from pytest import approx, fixture

from h2integrate.converters.heat.shell_tube_hx_cost_model import ShellTubeHXCostModel


@fixture
def shell_tube_hx_cost_model_config():
    cost_parameters = {
        "Q_ref": 1.0e6,
        "C_ref": 2.4e5,
        "exp_Q": 0.8,
        "cost_year": 2024,
    }

    tech_config = {
        "model_inputs": {
            "cost_parameters": cost_parameters,
        }
    }

    plant_config = {"plant": {"plant_life": 30}}
    return tech_config, plant_config


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

    def test_hx_cost_calculation(self, shell_tube_hx_cost_model_config):
        prob = self._create_problem(shell_tube_hx_cost_model_config)

        # Set input value for total heat transfer rate
        prob.set_val("Q_total_W", 5.0e6)  # 5 MW

        prob.run_model()

        CapEx_USD = prob.get_val("shell_tube_hx_cost.CapEx", units="USD")
        OpEx_USD_per_year = prob.get_val("shell_tube_hx_cost.OpEx", units="USD/year")

        expected_CapEx_USD = 240000.0 * (5.0e6 / 1.0e6) ** 0.8
        expected_OpEx_USD_per_year = 0.04 * expected_CapEx_USD

        assert CapEx_USD == approx(expected_CapEx_USD, rel=1e-5)
        assert OpEx_USD_per_year == approx(expected_OpEx_USD_per_year, rel=1e-5)
