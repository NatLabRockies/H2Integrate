import pytest
import numpy as np
import openmdao.api as om
from pytest import approx, fixture

from h2integrate.converters.heat.shell_tube_hx import ShellTubeHXPerformanceModel


@fixture
def shell_tube_hx_config():
    performance_parameters = {
        "process_fluid_temp_C": 90.0,
        "working_fluid_temp_C": 30.0,
        "process_fluid_mass_flow_kg_s": 18.0,
        "working_fluid_mass_flow_kg_s": 40.0,
        "process_fluid_pressure_bar": 1.0,
        "working_fluid_pressure_bar": 1.0,
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
            "performance_parameters": performance_parameters,
        }
    }
    plant_config = {
        "plant": {
            "simulation": {"n_timesteps": 1, "dt": 3600},
            "plant_life": 30,
        }
    }
    driver_config: dict = {}
    return tech_config, plant_config, driver_config


@pytest.mark.unit
class TestShellTubeHXPerformanceModel:
    def _create_problem(self, config):
        tech_config, plant_config, driver_config = config
        prob = om.Problem()
        prob.model.add_subsystem(
            "shell_tube_hx",
            ShellTubeHXPerformanceModel(
                tech_config=tech_config,
                plant_config=plant_config,
                driver_config=driver_config,
            ),
            promotes=["*"],
        )
        prob.setup()
        return prob

    def test_hx_performance_calculation(self, shell_tube_hx_config):
        prob = self._create_problem(shell_tube_hx_config)

        prob.run_model()

        # Multivariable-stream outlet values
        process_temp_out = prob.get_val(
            "shell_tube_hx.process_fluid:temperature_out", units="degC"
        )
        working_temp_out = prob.get_val(
            "shell_tube_hx.working_fluid:temperature_out", units="degC"
        )
        process_mass_flow_out = prob.get_val(
            "shell_tube_hx.process_fluid:mass_flow_out", units="kg/s"
        )
        working_mass_flow_out = prob.get_val(
            "shell_tube_hx.working_fluid:mass_flow_out", units="kg/s"
        )
        process_pressure_out = prob.get_val(
            "shell_tube_hx.process_fluid:pressure_out", units="bar"
        )
        working_pressure_out = prob.get_val(
            "shell_tube_hx.working_fluid:pressure_out", units="bar"
        )

        # Diagnostic scalar-like outputs (time-series of length 1)
        C_r = prob.get_val("shell_tube_hx.C_r")
        Ex_dest_dot_kW = prob.get_val("shell_tube_hx.Ex_dest_dot_kW", units="kW")
        NTU = prob.get_val("shell_tube_hx.NTU")
        Q_total_kW = prob.get_val("shell_tube_hx.Q_total_kW", units="kW")
        S_gen_dot_W_per_K = prob.get_val("shell_tube_hx.S_gen_dot_W_per_K", units="W/K")
        U_global_W_m2K = prob.get_val("shell_tube_hx.U_global_W_m2K", units="W/m**2/K")
        dp_working_Pa = prob.get_val("shell_tube_hx.pressure_drop_working_Pa", units="Pa")
        dp_process_Pa = prob.get_val("shell_tube_hx.pressure_drop_process_Pa", units="Pa")
        epsilon = prob.get_val("shell_tube_hx.epsilon")
        pump_power_kW = prob.get_val("shell_tube_hx.pump_power_kW", units="kW")

        # Expected values (regression values captured for this config)
        expected_C_r = 0.4527329816950921
        expected_Ex_dest_dot_kW = 248.78629912498585
        expected_NTU = 0.9142424832326593
        expected_Q_total_kW = 2462.235075109509
        expected_S_gen_dot_W_per_K = 834.433335988549
        expected_working_temp_out_C = 44.72803509154916
        expected_process_temp_out_C = 57.381403669025964
        expected_U_global_W_m2K = 1229.0775390792805
        expected_dp_working_Pa = 201.87162586061777
        expected_dp_process_Pa = 10251.659491792187
        expected_epsilon = 0.5421484468743297
        expected_pump_power_kW = 0.28157427036731625

        rel = 1e-5
        assert Q_total_kW[0] == approx(expected_Q_total_kW, rel=rel)
        assert U_global_W_m2K[0] == approx(expected_U_global_W_m2K, rel=rel)
        assert C_r[0] == approx(expected_C_r, rel=rel)
        assert Ex_dest_dot_kW[0] == approx(expected_Ex_dest_dot_kW, rel=rel)
        assert NTU[0] == approx(expected_NTU, rel=rel)
        assert S_gen_dot_W_per_K[0] == approx(expected_S_gen_dot_W_per_K, rel=rel)
        assert working_temp_out[0] == approx(expected_working_temp_out_C, rel=rel)
        assert process_temp_out[0] == approx(expected_process_temp_out_C, rel=rel)
        assert dp_working_Pa[0] == approx(expected_dp_working_Pa, rel=rel)
        assert dp_process_Pa[0] == approx(expected_dp_process_Pa, rel=rel)
        assert epsilon[0] == approx(expected_epsilon, rel=rel)
        assert pump_power_kW[0] == approx(expected_pump_power_kW, rel=rel)

        # Mass flow is conserved through the HX
        assert process_mass_flow_out[0] == approx(18.0, rel=1e-12)
        assert working_mass_flow_out[0] == approx(40.0, rel=1e-12)

        # Outlet pressure = inlet pressure − Δp (converted from Pa to bar)
        assert process_pressure_out[0] == approx(1.0 - expected_dp_process_Pa / 1e5, rel=rel)
        assert working_pressure_out[0] == approx(1.0 - expected_dp_working_Pa / 1e5, rel=rel)

    def test_hx_timeseries_shape(self, shell_tube_hx_config):
        """Confirm the model runs for n_timesteps > 1 and returns time-series outputs."""
        tech_config, plant_config, driver_config = shell_tube_hx_config
        # Bump n_timesteps and rerun
        plant_config = {
            "plant": {
                "simulation": {"n_timesteps": 3, "dt": 3600},
                "plant_life": 30,
            }
        }
        prob = om.Problem()
        prob.model.add_subsystem(
            "shell_tube_hx",
            ShellTubeHXPerformanceModel(
                tech_config=tech_config,
                plant_config=plant_config,
                driver_config=driver_config,
            ),
            promotes=["*"],
        )
        prob.setup()
        prob.run_model()

        Q = prob.get_val("shell_tube_hx.Q_total_kW", units="kW")
        assert Q.shape == (3,)
        # All timesteps use the same (config-default) inlets, so results are identical
        assert np.allclose(Q, Q[0])
