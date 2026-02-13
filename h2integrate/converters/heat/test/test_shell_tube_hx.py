import openmdao.api as om
from pytest import approx, fixture

from h2integrate.converters.heat.shell_tube_hx import ShellTubeHXPerformanceModel


@fixture
def shell_tube_hx_config():
    performance_parameterss = {
        "Th_in_C": 90.0,
        "Tc_in_C": 30.0,
        "m_dot_h_kg_s": 18.0,
        "m_dot_c_kg_s": 40.0,
        "N_tubes": 192,
        "N_passes": 2,
        "L_tube_m": 4.9,
        "D_o_m": 0.01905,
        "t_wall_m": 0.002,
        "D_shell_m": 0.591,
        "cost_year": 2024,
    }

    tech_config = {
        "model_inputs": {
            "performance_parameters": performance_parameterss,
        }
    }
    return tech_config


class TestShellTubeHXPerformanceModel:
    def _create_problem(self, config):
        prob = om.Problem()
        prob.model.add_subsystem(
            "shell_tube_hx",
            ShellTubeHXPerformanceModel(tech_config=config),
            promotes=["*"],
        )
        prob.setup()
        return prob

    def test_hx_performance_calculation(self, shell_tube_hx_config):
        prob = self._create_problem(shell_tube_hx_config)

        prob.run_model()

        C_r = prob.get_val("shell_tube_hx.C_r")
        Ex_dest_dot_kW = prob.get_val("shell_tube_hx.Ex_dest_dot_kW", units="kW")
        NTU = prob.get_val("shell_tube_hx.NTU")
        Q_total_kW = prob.get_val("shell_tube_hx.Q_total_kW", units="kW")
        S_gen_dot_W_per_K = prob.get_val("shell_tube_hx.S_gen_dot_W_per_K", units="W/K")
        Th_out_C = prob.get_val("shell_tube_hx.Th_out_C", units="C")
        Tc_out_C = prob.get_val("shell_tube_hx.Tc_out_C", units="C")
        U_global_W_m2K = prob.get_val("shell_tube_hx.U_global_W_m2K", units="W/m**2/K")
        dp_cold_Pa = prob.get_val("shell_tube_hx.dp_cold_Pa", units="Pa")
        dp_hot_Pa = prob.get_val("shell_tube_hx.dp_hot_Pa", units="Pa")
        epsilon = prob.get_val("shell_tube_hx.epsilon")
        pump_power_kW = prob.get_val("shell_tube_hx.pump_power_kW", units="kW")

        # Expected values can be adjusted based on known results or calculations
        expected_C_r = 0.4527329816950921
        expected_Ex_dest_dot_kW = 248.78629912498585
        expected_NTU = 0.9142424832326593
        expected_Q_total_kW = 2462.235075109509
        expected_S_gen_dot_W_per_K = 834.433335988549
        expected_Tc_out_C = 44.72803509154916
        expected_Th_out_C = 57.381403669025964
        expected_U_global_W_m2K = 1229.0775390792805
        expected_dp_cold_Pa = 201.87162586061777
        expected_dp_hot_Pa = 10251.659491792187
        expected_epsilon = 0.5421484468743297
        expected_pump_power_kW = 0.28157427036731625

        assert Q_total_kW == approx(expected_Q_total_kW, rel=1e-2)
        assert U_global_W_m2K == approx(expected_U_global_W_m2K, rel=1e-2)
        assert C_r == approx(expected_C_r, rel=1e-5)
        assert Ex_dest_dot_kW == approx(expected_Ex_dest_dot_kW, rel=1e-5)
        assert NTU == approx(expected_NTU, rel=1e-5)
        assert Q_total_kW == approx(expected_Q_total_kW, rel=1e-5)
        assert S_gen_dot_W_per_K == approx(expected_S_gen_dot_W_per_K, rel=1e-5)
        assert Tc_out_C == approx(expected_Tc_out_C, rel=1e-5)
        assert Th_out_C == approx(expected_Th_out_C, rel=1e-5)
        assert U_global_W_m2K == approx(expected_U_global_W_m2K, rel=1e-5)
        assert dp_cold_Pa == approx(expected_dp_cold_Pa, rel=1e-5)
        assert dp_hot_Pa == approx(expected_dp_hot_Pa, rel=1e-5)
        assert epsilon == approx(expected_epsilon, rel=1e-5)
        assert pump_power_kW == approx(expected_pump_power_kW, rel=1e-5)
